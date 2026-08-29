# What a stopped sequential test actually reports

Every rung of this ladder was verified with an SPRT, and every one of those
results was quoted with an Elo number next to it. This measures what those
numbers are.

A sequential test stops the moment the evidence crosses a boundary, and
crossing happens on a favourable run. The estimate at the stopping point is
therefore not the estimate the same games would have produced had they all been
played. That is a textbook property of sequential testing, not a bug. Its
*size*, for the rule this project actually used, was never measured.

Measuring it needs no engine games. The question is about the rule.

## Method, fixed before running

`scripts/sprt_bias.py` runs the project's own `Sprt` class against simulated
matches whose true difference is known: `elo0=0, elo1=100, alpha=beta=0.05,
max_games=600`, the configuration in every `sprt_match` and `ladder_sprt`
invocation. Draws follow the same Rao-Kupper form the test assumes, at the
pool's fitted 188 Elo (`docs/RATING_FIT.md`) rather than the 250 default, so
the simulation matches the games rather than the config. 3,000 matches per
point.

Both stopping modes are reported. Real runs played six games per batch and
could overshoot the boundary by up to five games; the difference between exact
and batched stopping belongs to how the runs were driven, not to the test.

**Showing bias** means the mean estimate among runs accepting H1, minus the
truth, being consistently positive beyond Monte Carlo error. **Showing none**
means it straddling zero.

## Result

Batched by six, as run:

| true difference | P(accept H1) | mean games | estimate given H1 | **bias** |
|---:|---:|---:|---:|---:|
| 0 | 3.0% | 70 | +92 | **+92** |
| 25 | 13.9% | 100 | +88 | **+63** |
| 50 | 48.6% | 129 | +78 | **+28** |
| 75 | 84.2% | 106 | +85 | **+10** |
| 100 | 96.9% | 72 | +102 | +2 |
| 150 | 99.9% | 41 | +139 | −11 |
| 200 | 100.0% | 28 | +183 | −17 |

Monte Carlo error is under 4 Elo everywhere; the pattern is not noise.

**The bias is large exactly where this project's questions live.** A real
difference of 25 to 50 Elo — the size of every evaluation change tested here,
and of the top rung transition — comes back reported as 78 to 88.

Above 100 the bias reverses slightly: the test stops so early that it
under-reports. That is the same mechanism with the boundary on the other side.

## The part that is worse than a bias

Condition on what actually happened in the ladder — the rule accepted H1 and
stopped **early** (L7 vs L6 stopped at 65 games):

| true difference | P(H1, ≤80 games) | estimate given that |
|---:|---:|---:|
| 0 | 2.1% | +113 |
| 25 | 7.8% | +108 |
| 50 | 20.3% | +108 |
| 75 | 40.6% | +111 |
| 100 | 66.0% | +118 |

**The reported number is about 110 whatever the truth is.** From a true
difference of zero to one of a hundred, the estimate an early-stopping run
reports moves by five Elo.

So a number quoted from an early-stopped SPRT is not an estimate of the
difference. It is approximately a constant — a property of where the boundary
sits, not of the engines.

What *does* carry information is whether the test accepted at all: 3% of the
time at a true zero, 49% at fifty, 97% at a hundred. **The verdict is
evidence. The number beside it is not.**

## What this does to the ladder table

The Elo column of the sequential ladder table — +361, +800, +361, +132, +361,
+93 — was produced by exactly this rule. Those figures should be read as
"the test stopped here", not as measurements of the gaps. The verdicts stand:
each rung really is above the one below, and that is what an SPRT is for.

It also settles a disagreement raised in `docs/RATING_FIT.md`. Fitting all
2,730 games jointly put L7 over L6 at **+50 [−3, +103]**, against the ladder
match's **+93** — and an outside engine that played both rungs put them 4 Elo
apart. The table above says a true difference near 50, passed through this
stopping rule and stopped early, reports about 108. **The direct match and the
cross-link were never in conflict.** One is a measurement and the other is the
output of a rule that reports roughly the same number regardless.

## What to do instead

Nothing here argues against sequential testing. It answers "is A better than
B" at a fraction of the cost of a fixed-length match, and this project's
ladder is verified because of it.

It argues against quoting the number it stops on. When a magnitude is the
deliverable — a slope, a conversion, an effect size — the match has to be
**fixed length with no stopping rule**, which is what `scripts/speed_elo.py`
did from the start and what `sprt_match --fixed` exists for.

The one direct check available agrees: the SEE pruning change measured **+73
[+20, +130]** sequentially and **+48 [+11, +87]** over 240 fixed games. A shift
of 25 Elo, in the direction this simulation predicts, in the one case where
both were run.
