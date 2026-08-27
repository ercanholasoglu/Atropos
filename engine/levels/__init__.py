"""Level registry and factory.

Levels are added here as each phase lands; asking for one that is not built
yet raises a clear error instead of silently falling back.
"""

from __future__ import annotations

from engine.base_engine import BaseEngine
from engine.levels.level1_random import Level1Random
from engine.levels.level2_material import Level2Material
from engine.levels.level3_minimax import Level3Minimax
from engine.levels.level4_alphabeta import Level4AlphaBeta
from engine.levels.level5_positional import Level5Positional
from engine.levels.level6_tactical import Level6Tactical
from engine.levels.level7_advanced import Level7Advanced
from engine.levels.level8_neural import Level8Neural
from engine.levels.search_engine import AdvancedEngine, SearchEngine
from engine.utils.constants import INITIAL_ELO, LEVEL_NAMES

LEVELS: dict[int, type[BaseEngine]] = {
    1: Level1Random,
    2: Level2Material,
    3: Level3Minimax,
    4: Level4AlphaBeta,
    5: Level5Positional,
    6: Level6Tactical,
    7: Level7Advanced,
    8: Level8Neural,
}

MAX_LEVEL = 8


def available_levels() -> list[int]:
    return sorted(LEVELS)


def create_engine(level: int, **kwargs) -> BaseEngine:
    """Instantiate the engine for ``level``."""
    if level not in LEVELS:
        if 1 <= level <= MAX_LEVEL:
            raise NotImplementedError(
                f"Level {level} ({LEVEL_NAMES.get(level, '?')}) is not implemented yet; "
                f"available: {available_levels()}"
            )
        raise ValueError(f"level must be 1..{MAX_LEVEL}, got {level}")
    return LEVELS[level](**kwargs)


__all__ = [
    "LEVELS",
    "MAX_LEVEL",
    "BaseEngine",
    "Level1Random",
    "Level2Material",
    "Level3Minimax",
    "Level4AlphaBeta",
    "Level5Positional",
    "Level6Tactical",
    "Level7Advanced",
    "Level8Neural",
    "SearchEngine",
    "AdvancedEngine",
    "INITIAL_ELO",
    "available_levels",
    "create_engine",
]
