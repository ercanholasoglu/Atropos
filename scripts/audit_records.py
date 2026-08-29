"""Which existing measurement records can be traced to a commit, and which cannot.

Telemetry does not work backwards. Every result recorded before it existed has
a number and no way to say which code produced it, and the honest response is
to mark those as unknown rather than to guess a commit from a file's timestamp
— the tree was dirty for most of this project's life, so even a correct
timestamp would name a commit the run did not actually use.

    python -m scripts.audit_records
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

UNKNOWN = "commit unknown"


def load(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def commit_of(record: dict) -> str | None:
    """The commit a record names, if it names one."""
    for key in ("commit", "git_commit", "revision"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit measurement records for provenance")
    parser.add_argument("--data", default="data")
    parser.add_argument("--write", action="store_true", help="stamp unknowns into the files")
    args = parser.parse_args()

    root = Path(args.data)
    records = sorted(p for p in root.rglob("*.json") if p.is_file())
    if not records:
        print(f"no records under {root}")
        return 0

    traced: list[tuple[Path, str]] = []
    untraced: list[Path] = []
    unreadable: list[Path] = []

    for path in records:
        data = load(path)
        if data is None:
            unreadable.append(path)
            continue
        commit = commit_of(data)
        (traced.append((path, commit)) if commit else untraced.append(path))

    print(f"{len(records)} record(s) under {root}/\n")
    print(f"traced to a commit: {len(traced)}")
    for path, commit in traced:
        print(f"  {commit:<10} {path}")

    print(f"\nno commit recorded: {len(untraced)}")
    for path in untraced:
        print(f"  {UNKNOWN:<10} {path}")
    if unreadable:
        print(f"\nunreadable: {len(unreadable)}")
        for path in unreadable:
            print(f"  {path}")

    if untraced:
        print(
            "\nThese predate telemetry. Their numbers are still valid measurements;\n"
            "what is missing is which code produced them, and that cannot be\n"
            "reconstructed — the working tree was dirty for most of this project,\n"
            "so dating a file to a commit would name one the run did not use."
        )

    if args.write:
        stamped = 0
        for path in untraced:
            data = load(path)
            if data is None:
                continue
            data["commit"] = None
            data["provenance"] = UNKNOWN
            data["provenance_note"] = (
                "Recorded before run telemetry existed. The commit is not "
                "recoverable and has been left null rather than guessed."
            )
            data["audited_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            path.write_text(json.dumps(data, indent=1))
            stamped += 1
        print(f"\nstamped {stamped} record(s) as '{UNKNOWN}'")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
