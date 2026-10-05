"""Semaine 1 : construire un dataset de positions annotées par Stockfish
à partir d'un dump PGN Lichess (.pgn ou .pgn.zst).
"""

from path import Path
import chess
import io

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