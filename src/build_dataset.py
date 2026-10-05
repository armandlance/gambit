"""Semaine 1 : construire un dataset de positions annotées par Stockfish
à partir d'un dump PGN Lichess (.pgn ou .pgn.zst).

Exemple :
    python src/build_dataset.py `
        --pgn data/raw/lichess_db_standard_rated_2013-01.pgn `
        --stockfish ""C:\Users\arman\Documents\stockfish\stockfish-windows-x86-64-universal.exe"" `
        --out data/processed/positions.csv `
        --max-positions 5000 --min-elo 1400 --max-elo 2200
"""
import argparse
import io
import random
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import pandas as pd
from tqdm import tqdm

PIECE_VALUES = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}


def open_pgn(path: Path):
    """Ouvre un PGN, en décompressant à la volée si c'est un .zst."""
    if path.suffix == ".zst":
        import zstandard as zstd

        reader = zstd.ZstdDecompressor().stream_reader(open(path, "rb"))
        return io.TextIOWrapper(reader, encoding="utf-8")
    return open(path, encoding="utf-8")


def non_pawn_material(board: chess.Board) -> int:
    return sum(
        value * len(board.pieces(piece_type, color))
        for piece_type, value in PIECE_VALUES.items()
        for color in (chess.WHITE, chess.BLACK)
    )


def game_phase(board: chess.Board) -> str:
    """Heuristique simple : ouverture / milieu de partie / finale."""
    if board.fullmove_number <= 10:
        return "opening"
    if non_pawn_material(board) <= 20:
        return "endgame"
    return "middlegame"


def keep_game(game: chess.pgn.Game, min_elo: int, max_elo: int) -> bool:
    h = game.headers
    try:
        white, black = int(h["WhiteElo"]), int(h["BlackElo"])
    except (KeyError, ValueError):
        return False
    if not (min_elo <= white <= max_elo and min_elo <= black <= max_elo):
        return False
    return h.get("Termination") == "Normal"


def analyse_position(engine, board, depth):
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].white()  # point de vue des Blancs
    pv = info.get("pv", [])
    best = pv[0] if pv else None
    return {
        "eval_cp": score.score(),  # None si mat forcé
        "mate_in": score.mate(),  # None si pas de mat forcé
        "best_move_uci": best.uci() if best else None,
        "best_move_san": board.san(best) if best else None,
        "pv_san": board.variation_san(pv[:5]) if pv else None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--pgn", type=Path, required=True)
    p.add_argument("--stockfish", type=str, required=True, help="chemin du binaire")
    p.add_argument("--out", type=Path, default=Path("data/processed/positions.csv"))
    p.add_argument("--max-positions", type=int, default=5000)
    p.add_argument("--positions-per-game", type=int, default=2)
    p.add_argument("--min-elo", type=int, default=1400)
    p.add_argument("--max-elo", type=int, default=2200)
    p.add_argument("--min-ply", type=int, default=8)
    p.add_argument("--depth", type=int, default=14)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    engine = chess.engine.SimpleEngine.popen_uci(args.stockfish)
    try:
        with open_pgn(args.pgn) as handle, tqdm(total=args.max_positions) as bar:
            while len(rows) < args.max_positions:
                game = chess.pgn.read_game(handle)
                if game is None:
                    break
                if not keep_game(game, args.min_elo, args.max_elo):
                    continue

                moves = list(game.mainline_moves())
                if len(moves) <= args.min_ply + 2:
                    continue
                candidates = list(range(args.min_ply, len(moves) - 1))
                k = min(args.positions_per_game, len(candidates))
                chosen = set(random.sample(candidates, k))

                board = game.board()
                for ply, move in enumerate(moves):
                    if ply in chosen and not board.is_game_over():
                        row = {
                            "game_id": game.headers.get("Site", "").split("/")[-1],
                            "fen": board.fen(),
                            "ply": ply,
                            "side_to_move": "white" if board.turn else "black",
                            "phase": game_phase(board),
                            "white_elo": int(game.headers["WhiteElo"]),
                            "black_elo": int(game.headers["BlackElo"]),
                            "played_move_uci": move.uci(),
                            "played_move_san": board.san(move),
                        }
                        row.update(analyse_position(engine, board, args.depth))
                        row["played_is_best"] = row["played_move_uci"] == row["best_move_uci"]
                        rows.append(row)
                        bar.update(1)
                    board.push(move)
    finally:
        engine.quit()

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    print(f"{len(df)} positions écrites dans {args.out}")
    if len(df):
        print(df["phase"].value_counts())


if __name__ == "__main__":
    main()