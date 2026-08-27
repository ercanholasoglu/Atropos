# Atropos roadmap

## Done

- Phase 0: CMake, tests, CI and UCI scaffold
- Phase 1: board state, FEN, legal move generation and make/unmake
- Phase 2: perft and known-node regression fixtures
- Phase 3: material evaluation and fixed-depth negamax
- Phase 4: move ordering and quiescence search
- Phase 5: node/time search limits
- Phase 6: worker-thread UCI search and cooperative stop
- Phase 7: iterative deepening and per-depth UCI info
- Phase 8: transposition table and TT move ordering
- Phase 9: killer moves and history heuristic
- Phase 10: handcrafted evaluation v2
- Phase 11: benchmark command and tactical regression suite
- Phase 12: UCI infinite, ponderhit and improved clock parsing
- Phase 13: cached Zobrist hash updates
- Phase 14: allocation-light move generation APIs and search move buffers
- Phase 15: deterministic self-play strength tracking harness
- Phase 16: external gauntlet script and match score parsing

## Remaining Core Engine Work

1. Strength tracking v3: SPRT-style gates and historical rating logs
2. Evaluation v3: tapered eval, passed pawns, open files and richer king safety
3. Tactical suite expansion and benchmark baselines
4. Richer tournament time management and ponder policy
5. Deeper performance work: compact move storage, profiling and branch hot spots

## Research Work

1. NNUE feature extraction
2. NNUE inference runtime
3. Training data generation
4. Training and quantization scripts
5. Eval blending and ablation tests

## Rough Remaining Effort

- Usable hobby engine: 3-5 more focused phases
- Reasonably testable engine: 6-8 more focused phases
- Research-grade NNUE engine: 12+ focused phases
