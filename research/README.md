# Research modules

Five experiments on top of the engine ladder. The ladder is what makes them
measurable: every idea here is judged by games against Levels 1–7, not by a
training curve.

## Status

| Module | Purpose | State |
|--------|---------|-------|
| `features.py`, `params.py` | Shared foundation: 384/768-dim features, parameterised evaluation | ✅ built |
| `rl_tuning/` | Policy-gradient tuning of evaluation parameters | ✅ built |
| `self_play/` | TDLeaf(λ) value learning from self-play | ✅ built |
| `hybrid_eval/` | Classical + NN + LLM tiers, routed by position complexity | ✅ built |
| `minimal_nnue/` | Smallest NNUE that reaches a target Elo | ✅ built |
| `alphazero_lite/` | Small ResNet + MCTS, trainable on an M2 Pro | ✅ built |

## The foundation the modules share

`features.py` turns a position into numbers and `params.py` turns the
evaluation into a vector. Two properties make everything above them
comparable, and both are asserted by tests:

* `piece_square_vector(board) @ pst_weights()` reproduces the engine's own
  piece-square score **exactly**, in both phases. Anything learned can be read
  in the same units as the hand-written tables and put next to them.
* `EvalParams()` with its default values reproduces `positional_eval`
  **exactly**. The decomposition into material + placement + structure is
  algebraically exact, not an approximation, so "did tuning help?" has a clean
  answer rather than a confounded one.

## What the first runs showed

**Learning from all-zero weights does not work, for a reason worth writing
down.** An evaluation that scores every position at zero plays randomly,
random games almost never finish decisively inside a move limit, and a run of
draws carries no gradient at all — the first TD run reported an average
temporal difference of exactly 0.0000 across every game. Seeding the material
values and leaving placement flat fixes the cold start and sharpens the
question to one self-play can actually answer: *can it rediscover where the
pieces belong?*

**It cannot, at 60 games.** After 60 self-play games at depth 2 the knight's
centre-minus-rim weight had moved by −0.3 centipawns, against the 70 the
hand-written table uses. The mechanism is sound — the temporal differences are
non-zero, the updates land, the directional tests pass — but the sample is two
or three orders of magnitude short.

### Ten thousand games

`make self-play` ran 10,000 games in 34 minutes (2,125 White wins, 2,064 Black,
5,811 draws). The learned tables look nothing like the hand-written ones:

| piece | learned centre−rim | reference | shape correlation |
|---|---:|---:|---:|
| pawn | −60.7 | 22.5 | 0.456 |
| knight | −13.9 | **70.0** | −0.160 |
| bishop | −12.5 | 30.0 | −0.178 |
| rook | −12.0 | 0.0 | 0.122 |
| queen | −5.3 | 25.0 | 0.040 |
| king | −6.4 | −40.0 | 0.269 |

The knight's centre-minus-rim even moved the *wrong way* — it was climbing
early (+2.2 at 100 games, +8.9 at 300) and then reversed.

But resemblance was never the measure. Playing strength was:

| 64 games, 0.2s per move | score | Elo |
|---|---:|---:|
| learned vs its material-only starting point | 59.4% (+33 =10 −21) | **+66** |
| learned vs the hand-written tables | 40.6% (+21 =10 −33) | **−66** |

So TD did learn: it beats where it started. And it fell short: the tables a
person wrote in an afternoon still beat 34 minutes of self-play. The learned
table sits about midway between the two, and it got there by a route that has
almost nothing in common with the human one.

**A note on sample size, because this run supplies its own cautionary tale.**
The first pass used 16 games and read 65.6% / 53.1% — "clearly better than its
start, level with the hand-written tables". At 64 games the same weights read
59.4% / 40.6%. Both small-sample numbers flattered the learned table, and the
second one flattered it enough to invert the conclusion. One standard error on
a 16-game match is 12.5%; the effect being measured was 9.4. At ~0.17s per game that is minutes, not
days, so the run is affordable — `make self-play` makes it.

`scripts/self_play_run.py` runs ten thousand games and ends by asking the only
question that settles the matter: **does the learned table play better?** A
table that correlates with the hand-written one but loses to it has not learned
chess, and one that looks nothing like it but wins has. It also reports shape
correlation with the engine's tables *after removing each table's mean*, since
the mean is the piece value — which was seeded rather than learned, and would
otherwise inflate every correlation to nearly one.

## Decisions to make before writing code

**1. PyTorch or numpy — settled.** torch 2.13.0 is installed and MPS is
available on this M2 Pro (10 cores). It is needed for
`alphazero_lite` (a 4-block ResNet is not something to hand-differentiate) and
makes `minimal_nnue` far easier at the 270K-parameter end. `rl_tuning`,
`self_play` and `hybrid_eval` need nothing but numpy — a TD(λ) linear
evaluator and a perturbation-based optimiser have closed-form updates.

The split stands: numpy for the three that do not need autograd, torch (the
`research` extra) for the two that do.

**2. The real constraint is self-play throughput, not model size.**
python-chess runs at roughly 80–250k nodes/second, so a Level-4-strength
self-play game at 0.1s/move takes ~20 seconds. That is ~180 games/hour on one
core, ~1500/hour across the 10 cores. Every module below is budgeted against
that number, and it is why the ladder — cheap, deterministic opponents at
known strengths — is the reward signal rather than a held-out dataset.

**3. "Policy gradient" over parameters is perturbation-based.** Sampling
parameter vectors from a Gaussian and weighting them by match results *is*
REINFORCE, and it is a close relative of the SPSA that real engines tune
with. Worth implementing as policy gradient and saying so, rather than
implying a different algorithm is at work.

## Planned shape

```
research/
  rl_tuning/parameter_optimizer.py    Gaussian policy over eval params,
                                      reward = score against a fixed baseline
  self_play/value_learner.py          TD(λ) with eligibility traces over a
                                      feature vector; linear first, then MLP
  minimal_nnue/architecture_search.py 6 architectures, 768 → 270K params,
                                      ablation over input feature sets
  hybrid_eval/tiered_evaluator.py     complexity estimate → tier, under a
                                      latency budget; LLM tier optional
  alphazero_lite/                     4-block ResNet, 400 MCTS simulations
notebooks/                            one per module: experiments, plots,
                                      ablation tables
```


## Minimal NNUE — what the search found

5,878 positions from 80 self-play games, labelled by distillation (the
engine's own evaluation after a quiescence search settles the position, clamped
to ±1500cp). Six architectures, 60 epochs each, all on the same positions.

```
architecture        params   val MSE   MAE cp  vs mean  1-pos µs  batch µs
--------------------------------------------------------------------------
linear-folded          385    0.0916    357.7    585.3       4.9      0.02
linear-planes          769    0.0902    358.9    585.3       5.1      0.02
mlp-16              12,321    0.0394    216.0    585.3      10.2      0.20
mlp-32x32           25,697    0.0353    180.9    585.3      17.5      0.35
mlp-128             98,561    0.0299    160.3    585.3      13.1      0.25
nnue-336x32        269,201    0.0304    185.3    585.3      22.5      0.79
```

Three findings, in order of how much they matter:

**1. The latency column decides the argument.** The hand-written evaluation
costs **6.4µs** per position. Every network that meaningfully beats the linear
baseline costs 10–22µs — two to four times the entire evaluation it would
replace. A search evaluates hundreds of thousands of leaves per move, so that
is a straight trade of depth for accuracy, and in this range depth wins. At
this scale, in this language, an NNUE cannot pay for itself inside the search.
The batch column shows why that is a Python problem and not a network one:
amortised over a batch the same forward pass costs 0.02–0.8µs.

**2. The linear models are the only free ones.** A linear model over
piece-square features *is* a piece-square table — it folds into the lookup the
engine already walks and costs nothing extra per leaf. It is also barely better
than predicting the mean (358cp against a 585cp baseline), which is the real
answer to "how small can this be": small enough to be free, and then it is not
worth having.

**3. Bigger stopped helping around 100K parameters.** `nnue-336x32` has 2.7×
the parameters of `mlp-128` and a worse validation error. With 4,700 training
positions that is undertrained rather than a statement about the architecture —
but it does mean the ceiling here is data, not capacity.

### Input-feature ablation

Network held fixed at 768→32→32→1, only the input varied:

```
encoding             params   val MSE   MAE cp
----------------------------------------------
folded               13,409    0.0344    157.7
planes               25,697    0.0353    180.9
planes+phase         25,729    0.0355    184.5
planes+handcrafted   25,953    0.0348    187.7
```

**Colour symmetry is worth more than the freedom to break it.** The folded
384-wide encoding beats the 768-wide one with half the parameters. Separate
planes per colour let the network learn that a white knight on e4 differs from
a black knight on e5; at this data scale that freedom costs more than it earns,
and the mirror is the better prior.

Adding the game phase or the handcrafted terms made it slightly *worse* — both
are functions of the board the network can already see, so they add parameters
and no information.


## AlphaZero-lite — what the build decided

**The move encoding is 96% of the design.** The obvious choice is one policy
output per `from × to` pair — 4,096 of them, simple to write. Producing that
needs a dense layer from the tower's flattened features, which costs **8.4
million parameters**: the policy head becomes 96% of the model and the
residual tower it is supposed to read becomes a rounding error. AlphaZero's
8×8×73 scheme is produced by a 1×1 convolution instead, ~4,700 parameters,
and gets underpromotion for free.

| | flat `from × to` | AlphaZero 8×8×73 |
|---|---:|---:|
| policy outputs | 4,096 | 4,672 |
| total network parameters | 8,735,249 | **345,178** |
| underpromotion | collapsed to queen | encoded |

25× smaller, and the difference is entirely in a layer that was never doing
any thinking.

**A test found a real encoding bug.** The direction-and-distance encoder
checked that a move *pointed* along one of the eight rays, not that it
*landed* on it — so a1–c4 silently encoded as a1–d4's index. No legal chess
move can trigger it (queens and bishops always land on their ray), which is
exactly why it would have survived. A sweep over 8,945 legal moves from 300
random positions is now a permanent test.

**MCTS is validated without the network.** With a uniform evaluator — flat
priors, every position scored as a draw — the search still finds mate in one.
Nothing but correct selection and correct sign-flipping on backup can produce
that, which makes it the sharpest available check on the tree.

### The budget, measured

| | |
|---|---|
| network forward pass, one position | 1.0 ms |
| batched over 64 | 0.34 ms per position |
| MCTS, per simulation | ~1.2 ms |
| 400 simulations per move | ~0.5 s |
| one 80-move self-play game | ~40 s |
| one core, one hour | ~90 games |
| ten cores, one day | ~20,000 games |

AlphaZero used forty million games. Two things follow, and both are already
in the code: the network is sized so that a few thousand games can fill it
rather than be memorised by it, and the evaluator exposes a batch interface
because a 3× speedup is sitting there for whoever implements virtual-loss
parallel MCTS.
