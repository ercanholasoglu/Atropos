"""Board rendering.

Two boards for two jobs: an SVG one for watching and analysing, where it only
has to look right, and a grid of buttons for playing, where Streamlit has no
drag-and-drop and clicking squares is the closest thing to picking up a piece.
"""

from __future__ import annotations

import chess
import chess.svg
import streamlit as st

# Unicode chess figurines. Both colours use the solid glyphs — the hollow
# white ones vanish against a light square on most fonts.
PIECE_GLYPHS = {
    (chess.PAWN, chess.WHITE): "♟",
    (chess.KNIGHT, chess.WHITE): "♞",
    (chess.BISHOP, chess.WHITE): "♝",
    (chess.ROOK, chess.WHITE): "♜",
    (chess.QUEEN, chess.WHITE): "♛",
    (chess.KING, chess.WHITE): "♚",
    (chess.PAWN, chess.BLACK): "♟",
    (chess.KNIGHT, chess.BLACK): "♞",
    (chess.BISHOP, chess.BLACK): "♝",
    (chess.ROOK, chess.BLACK): "♜",
    (chess.QUEEN, chess.BLACK): "♛",
    (chess.KING, chess.BLACK): "♚",
}

EMPTY_GLYPH = "·"
TARGET_GLYPH = "•"

_BOARD_CSS = """
<style>
div[data-testid="stHorizontalBlock"] div.board-square button {
    width: 100%;
    aspect-ratio: 1 / 1;
    font-size: 1.9rem;
    line-height: 1;
    padding: 0;
    border-radius: 0;
    border: none;
}
</style>
"""


def render_svg_board(
    board: chess.Board,
    lastmove: chess.Move | None = None,
    orientation: chess.Color = chess.WHITE,
    size: int = 420,
    arrows: list | None = None,
) -> None:
    """Draw a static board, with the last move and any check highlighted."""
    check_square = board.king(board.turn) if board.is_check() else None
    svg = chess.svg.board(
        board=board,
        lastmove=lastmove,
        orientation=orientation,
        check=check_square,
        size=size,
        arrows=arrows or [],
    )
    st.markdown(
        f'<div style="display:flex;justify-content:center">{svg}</div>',
        unsafe_allow_html=True,
    )


def square_label(board: chess.Board, square: chess.Square, is_target: bool) -> str:
    """What to print on a square's button."""
    piece = board.piece_at(square)
    if piece is not None:
        glyph = PIECE_GLYPHS[(piece.piece_type, piece.color)]
        # A black piece keeps the glyph; the colour comes from the prefix so
        # the two sides stay apart in a monochrome button.
        return glyph if piece.color == chess.BLACK else f"{glyph}̲"
    return TARGET_GLYPH if is_target else EMPTY_GLYPH


def render_interactive_board(
    board: chess.Board,
    selected: chess.Square | None,
    orientation: chess.Color = chess.WHITE,
    key_prefix: str = "sq",
    disabled: bool = False,
) -> chess.Square | None:
    """A clickable board. Returns the square the user pressed, if any.

    Clicking is two steps — a piece, then a destination — so the caller keeps
    the selected square and decides whether the pair makes a legal move.
    """
    st.markdown(_BOARD_CSS, unsafe_allow_html=True)

    targets = set()
    if selected is not None:
        targets = {m.to_square for m in board.legal_moves if m.from_square == selected}

    ranks = range(7, -1, -1) if orientation == chess.WHITE else range(8)
    files = range(8) if orientation == chess.WHITE else range(7, -1, -1)

    clicked: chess.Square | None = None
    for rank in ranks:
        columns = st.columns(8, gap=None)
        for column, file in zip(columns, files):
            square = chess.square(file, rank)
            with column:
                st.markdown('<div class="board-square">', unsafe_allow_html=True)
                pressed = st.button(
                    square_label(board, square, square in targets),
                    key=f"{key_prefix}_{square}",
                    use_container_width=True,
                    type="primary" if square == selected or square in targets else "secondary",
                    disabled=disabled,
                    help=chess.square_name(square),
                )
                st.markdown("</div>", unsafe_allow_html=True)
                if pressed:
                    clicked = square
    return clicked


def promotion_choice(key: str = "promotion") -> chess.PieceType:
    """Which piece a pawn reaching the last rank becomes."""
    labels = {
        "Queen": chess.QUEEN,
        "Rook": chess.ROOK,
        "Bishop": chess.BISHOP,
        "Knight": chess.KNIGHT,
    }
    choice = st.selectbox("Promote to", list(labels), key=key)
    return labels[choice]
