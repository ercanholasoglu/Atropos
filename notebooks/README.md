# Research notebooks

One per research module. Each runs its experiment for real — the numbers and
charts below are produced by the code in `research/`, not copied in — and each
ends by saying what the result does *not* show, which at these budgets is
usually the more useful half.

| Notebook | Module | The finding |
|---|---|---|
| [01_rl_tuning](01_rl_tuning.ipynb) | `research/rl_tuning` | Policy gradient over evaluation parameters, and why the noise floor of a 4-game match swamps the effects being chased |
| [02_self_play](02_self_play.ipynb) | `research/self_play` | TDLeaf(λ) from self-play — including the cold start, where all-zero weights produce a mean temporal difference of exactly 0.0000 |
| [03_minimal_nnue](03_minimal_nnue.ipynb) | `research/minimal_nnue` | Six architectures, 385 → 269K parameters, and the latency column that decides the argument |
| [04_hybrid_eval](04_hybrid_eval.ipynb) | `research/hybrid_eval` | Complexity-based tier routing under a latency budget, and why it belongs at the root rather than the leaf |
| [05_alphazero_lite](05_alphazero_lite.ipynb) | `research/alphazero_lite` | A 4-block ResNet and PUCT, the move encoding that costs 25× the parameters, and the self-play budget everything follows from |

## Running them

```bash
make notebooks        # execute all five in place, outputs embedded
```

Measured on an M2 Pro, one at a time and with nothing else running:

| Notebook | Wall clock |
|---|---:|
| 01_rl_tuning | 4 min |
| 02_self_play | 21 s |
| 03_minimal_nnue | 39 s |
| 04_hybrid_eval | 7 s |
| 05_alphazero_lite | 31 s |

Run them in parallel with anything else and 01 stretches badly — it is a
self-play loop that wants a whole core, and its CPU time stays flat while its
wall clock does not.

Or open one directly:

```bash
.venv/bin/jupyter lab notebooks/
```

They import from the repository root by putting the parent directory on
`sys.path`, so they work from a checkout without installing the package.

## A note on the numbers

Every experiment here is sized to finish in a notebook — minutes, not days.
That is enough to show that the machinery works and to measure what the real
experiment would cost; it is not enough to make the machinery *work well*, and
each notebook says so where it applies. The throughput figures at the end of
02 and 05 are the ones to read if you want to know what a serious run needs.
