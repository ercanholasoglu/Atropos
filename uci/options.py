"""Engine options, and the one that makes this engine unusual.

Most of these are the options every UCI engine has. ``Level`` is the one that
matters here: this project is a ladder of eight engines, not one, and exposing
the rung as an option is what lets an external tool play any of them. Without
it the ladder is only measurable against itself.
"""

from __future__ import annotations

from dataclasses import dataclass

from engine.levels import MAX_LEVEL, available_levels


@dataclass
class EngineOptions:
    hash_mb: int = 16
    level: int = 7
    # Time deducted from every allocation to cover the round trip to the GUI.
    # Losing on time with a won position is the most avoidable loss there is.
    move_overhead_ms: int = 30
    ponder: bool = False
    threads: int = 1

    def clamp(self) -> "EngineOptions":
        self.hash_mb = max(1, min(self.hash_mb, 1024))
        self.level = max(1, min(self.level, MAX_LEVEL))
        if self.level not in available_levels():
            self.level = max(available_levels())
        self.move_overhead_ms = max(0, min(self.move_overhead_ms, 5000))
        self.threads = 1  # declared honestly: the search is single-threaded
        return self


@dataclass(frozen=True)
class OptionDescription:
    name: str
    type: str
    default: str
    minimum: int | None = None
    maximum: int | None = None

    def to_uci(self) -> str:
        parts = [f"option name {self.name} type {self.type} default {self.default}"]
        if self.minimum is not None:
            parts.append(f"min {self.minimum}")
        if self.maximum is not None:
            parts.append(f"max {self.maximum}")
        return " ".join(parts)


def describe_options(defaults: EngineOptions | None = None) -> list[OptionDescription]:
    defaults = defaults or EngineOptions()
    return [
        OptionDescription("Hash", "spin", str(defaults.hash_mb), 1, 1024),
        OptionDescription("Level", "spin", str(defaults.level), 1, MAX_LEVEL),
        OptionDescription("Move Overhead", "spin", str(defaults.move_overhead_ms), 0, 5000),
        OptionDescription("Ponder", "check", "true" if defaults.ponder else "false"),
        OptionDescription("Threads", "spin", "1", 1, 1),
    ]


def set_option(options: EngineOptions, name: str, value: str) -> bool:
    """Apply one ``setoption``. Returns whether it was understood."""
    key = name.strip().lower()
    text = value.strip()

    if key == "hash":
        return _set_int(options, "hash_mb", text)
    if key == "level":
        return _set_int(options, "level", text)
    if key == "move overhead":
        return _set_int(options, "move_overhead_ms", text)
    if key == "threads":
        return _set_int(options, "threads", text)
    if key == "ponder":
        options.ponder = text.lower() in ("true", "1", "yes", "on")
        options.clamp()
        return True
    return False


def parse_setoption(args: tuple[str, ...] | list[str]) -> tuple[str, str] | None:
    """Split ``name <words> value <words>``.

    Option names contain spaces ("Move Overhead"), so this cannot be done by
    position — the ``value`` keyword is the only reliable separator, and an
    option set to nothing is a legitimate button press.
    """
    tokens = [str(token) for token in args]
    lowered = [token.lower() for token in tokens]
    if "name" not in lowered:
        return None

    name_index = lowered.index("name")
    value_index = lowered.index("value") if "value" in lowered else None
    name = " ".join(
        tokens[name_index + 1 : value_index if value_index is not None else len(tokens)]
    )
    value = " ".join(tokens[value_index + 1 :]) if value_index is not None else ""
    return (name, value) if name else None


def _set_int(options: EngineOptions, field: str, text: str) -> bool:
    """Assign an integer option, ignoring a value that is not one.

    A GUI sending nonsense should leave the engine on its previous setting,
    not crash it out of the game.
    """
    try:
        value = int(text)
    except ValueError:
        return False
    setattr(options, field, value)
    options.clamp()
    return True
