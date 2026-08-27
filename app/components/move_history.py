"""Move list and PGN export."""

from __future__ import annotations

import streamlit as st

from engine.board import ChessGame


def move_pairs(san_moves: list[str]) -> list[tuple[int, str, str]]:
    """SAN moves regrouped into numbered pairs for display."""
    pairs = []
    for index in range(0, len(san_moves), 2):
        number = index // 2 + 1
        white = san_moves[index]
        black = san_moves[index + 1] if index + 1 < len(san_moves) else ""
        pairs.append((number, white, black))
    return pairs


def render_move_history(game: ChessGame, height: int = 260) -> None:
    if not game.moves:
        st.caption("No moves yet.")
        return

    rows = "".join(
        f"<tr><td style='opacity:.5;width:2.5rem'>{number}.</td>"
        f"<td style='width:5rem'>{white}</td><td>{black}</td></tr>"
        for number, white, black in move_pairs(game.move_history_san())
    )
    st.markdown(
        f"""<div style="height:{height}px;overflow-y:auto;font-variant-numeric:tabular-nums">
            <table style="width:100%;border-collapse:collapse">{rows}</table></div>""",
        unsafe_allow_html=True,
    )


def render_pgn_download(game: ChessGame, white: str, black: str, key: str = "pgn") -> None:
    pgn = game.to_pgn(white=white, black=black)
    st.download_button(
        "Download PGN",
        data=pgn,
        file_name="game.pgn",
        mime="application/x-chess-pgn",
        key=key,
        use_container_width=True,
    )
    with st.expander("PGN"):
        st.code(pgn, language="text")
