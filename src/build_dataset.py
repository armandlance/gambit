"""Semaine 1 : construire un dataset de positions annotées par Stockfish
à partir d'un dump PGN Lichess (.pgn ou .pgn.zst).
"""
import io
from path import Path

import chess
import chess.engine
import chess.pgn


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