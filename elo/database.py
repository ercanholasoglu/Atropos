"""SQLite storage for engines, games and rating history.

Three tables, one job each: ``engines`` holds the current rating and record,
``games`` is the immutable log of what happened, and ``elo_history`` is the
per-game rating trail the charts are drawn from.

Every rating in ``engines`` is derivable by replaying ``games``, which is
deliberate: the log is the source of truth and the summary is a cache that
can be rebuilt.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = "data/elo.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS engines (
    id            INTEGER PRIMARY KEY,
    name          TEXT UNIQUE NOT NULL,
    level         INTEGER NOT NULL,
    elo           REAL NOT NULL,
    initial_elo   REAL NOT NULL,
    games_played  INTEGER NOT NULL DEFAULT 0,
    wins          INTEGER NOT NULL DEFAULT 0,
    losses        INTEGER NOT NULL DEFAULT 0,
    draws         INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    id               INTEGER PRIMARY KEY,
    white_engine     TEXT NOT NULL,
    black_engine     TEXT NOT NULL,
    result           TEXT NOT NULL CHECK (result IN ('1-0', '0-1', '1/2-1/2')),
    white_elo_before REAL NOT NULL,
    black_elo_before REAL NOT NULL,
    white_elo_after  REAL NOT NULL,
    black_elo_after  REAL NOT NULL,
    pgn              TEXT,
    moves_count      INTEGER NOT NULL DEFAULT 0,
    opening          TEXT,
    termination      TEXT,
    event            TEXT,
    played_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS elo_history (
    id          INTEGER PRIMARY KEY,
    engine_name TEXT NOT NULL,
    elo         REAL NOT NULL,
    game_id     INTEGER,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (game_id) REFERENCES games (id)
);

CREATE INDEX IF NOT EXISTS idx_games_white ON games (white_engine);
CREATE INDEX IF NOT EXISTS idx_games_black ON games (black_engine);
CREATE INDEX IF NOT EXISTS idx_history_engine ON elo_history (engine_name, id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EloDatabase:
    """Rating storage. Every method opens its own connection.

    Streamlit reruns scripts and reuses threads unpredictably, so a
    long-lived connection would be a source of cross-thread bugs for no gain
    at this scale.
    """

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.in_memory = str(db_path) == ":memory:"
        # An in-memory database lives inside its connection, so that one case
        # has to hold the connection open — closing it would drop the schema.
        self._shared: sqlite3.Connection | None = None
        if self.in_memory:
            self._shared = self._new_connection()
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _new_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        if self._shared is not None:
            yield self._shared
            self._shared.commit()
            return
        conn = self._new_connection()
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def close(self) -> None:
        """Release the in-memory connection; a no-op for file databases."""
        if self._shared is not None:
            self._shared.close()
            self._shared = None

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    # --- engines ----------------------------------------------------------

    def register_engine(self, name: str, level: int, initial_elo: float) -> int:
        """Add an engine, or return the existing one's id untouched.

        Registering is idempotent: re-running a tournament script must not
        reset a rating that games have already moved.
        """
        now = _now()
        with self.connect() as conn:
            existing = conn.execute("SELECT id FROM engines WHERE name = ?", (name,)).fetchone()
            if existing:
                return int(existing["id"])
            cursor = conn.execute(
                """INSERT INTO engines
                   (name, level, elo, initial_elo, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, level, initial_elo, initial_elo, now, now),
            )
            engine_id = int(cursor.lastrowid or 0)
            conn.execute(
                "INSERT INTO elo_history (engine_name, elo, game_id, recorded_at) VALUES (?, ?, NULL, ?)",
                (name, initial_elo, now),
            )
            return engine_id

    def get_engine(self, name: str) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM engines WHERE name = ?", (name,)).fetchone()
            return dict(row) if row else None

    def get_rating(self, name: str) -> float | None:
        engine = self.get_engine(name)
        return engine["elo"] if engine else None

    def list_engines(self) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM engines ORDER BY level").fetchall()
            return [dict(row) for row in rows]

    # --- games ------------------------------------------------------------

    def record_game(
        self,
        white: str,
        black: str,
        result: str,
        white_elo_before: float,
        black_elo_before: float,
        white_elo_after: float,
        black_elo_after: float,
        pgn: str = "",
        moves_count: int = 0,
        opening: str = "",
        termination: str = "",
        event: str = "",
    ) -> int:
        """Write one game and move both engines' records in the same transaction."""
        if result not in ("1-0", "0-1", "1/2-1/2"):
            raise ValueError(f"invalid result {result!r}")
        now = _now()

        with self.connect() as conn:
            cursor = conn.execute(
                """INSERT INTO games (white_engine, black_engine, result,
                       white_elo_before, black_elo_before, white_elo_after,
                       black_elo_after, pgn, moves_count, opening, termination,
                       event, played_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    white,
                    black,
                    result,
                    white_elo_before,
                    black_elo_before,
                    white_elo_after,
                    black_elo_after,
                    pgn,
                    moves_count,
                    opening,
                    termination,
                    event,
                    now,
                ),
            )
            game_id = int(cursor.lastrowid or 0)

            white_w, white_l, white_d = _wld(result, as_white=True)
            black_w, black_l, black_d = _wld(result, as_white=False)
            for name, elo, (won, lost, drew) in (
                (white, white_elo_after, (white_w, white_l, white_d)),
                (black, black_elo_after, (black_w, black_l, black_d)),
            ):
                conn.execute(
                    """UPDATE engines
                          SET elo = ?, games_played = games_played + 1,
                              wins = wins + ?, losses = losses + ?, draws = draws + ?,
                              updated_at = ?
                        WHERE name = ?""",
                    (elo, won, lost, drew, now, name),
                )
                conn.execute(
                    "INSERT INTO elo_history (engine_name, elo, game_id, recorded_at) VALUES (?, ?, ?, ?)",
                    (name, elo, game_id, now),
                )
            return game_id

    def get_game(self, game_id: int) -> dict | None:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
            return dict(row) if row else None

    def get_games(self, engine_name: str | None = None, limit: int | None = None) -> list[dict]:
        query = "SELECT * FROM games"
        params: list = []
        if engine_name:
            query += " WHERE white_engine = ? OR black_engine = ?"
            params += [engine_name, engine_name]
        query += " ORDER BY id DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(query, params).fetchall()]

    def game_count(self) -> int:
        with self.connect() as conn:
            return int(conn.execute("SELECT COUNT(*) FROM games").fetchone()[0])

    # --- reporting --------------------------------------------------------

    def get_leaderboard(self) -> list[dict]:
        """Engines by rating, with a score percentage and a rank."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT name, level, elo, initial_elo, games_played, wins, losses, draws
                     FROM engines
                    ORDER BY elo DESC, level DESC"""
            ).fetchall()

        board = []
        for rank, row in enumerate(rows, start=1):
            entry = dict(row)
            played = entry["games_played"]
            entry["rank"] = rank
            entry["points"] = entry["wins"] + 0.5 * entry["draws"]
            entry["score_pct"] = entry["points"] / played if played else 0.0
            entry["elo_change"] = entry["elo"] - entry["initial_elo"]
            board.append(entry)
        return board

    def get_elo_history(self, engine_name: str) -> list[dict]:
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT elo, game_id, recorded_at FROM elo_history
                    WHERE engine_name = ? ORDER BY id""",
                (engine_name,),
            ).fetchall()
            return [dict(row) for row in rows]

    def head_to_head(self, engine_a: str, engine_b: str) -> dict:
        """A's record against B, both colours pooled."""
        with self.connect() as conn:
            rows = conn.execute(
                """SELECT white_engine, result FROM games
                    WHERE (white_engine = ? AND black_engine = ?)
                       OR (white_engine = ? AND black_engine = ?)""",
                (engine_a, engine_b, engine_b, engine_a),
            ).fetchall()

        wins = losses = draws = 0
        for row in rows:
            a_is_white = row["white_engine"] == engine_a
            if row["result"] == "1/2-1/2":
                draws += 1
            elif (row["result"] == "1-0") == a_is_white:
                wins += 1
            else:
                losses += 1

        played = wins + losses + draws
        return {
            "engine_a": engine_a,
            "engine_b": engine_b,
            "games": played,
            "wins": wins,
            "losses": losses,
            "draws": draws,
            "score": (wins + 0.5 * draws) / played if played else 0.0,
        }

    def reset(self) -> None:
        """Drop every row. Used by tests and the "start over" button."""
        with self.connect() as conn:
            conn.executescript("DELETE FROM elo_history; DELETE FROM games; DELETE FROM engines;")


def _wld(result: str, as_white: bool) -> tuple[int, int, int]:
    """(win, loss, draw) flags for one side of a result."""
    if result == "1/2-1/2":
        return 0, 0, 1
    white_won = result == "1-0"
    won = white_won if as_white else not white_won
    return (1, 0, 0) if won else (0, 1, 0)
