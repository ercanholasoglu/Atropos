# Pre-registration: does strength track the collapse or the game count?

Written before the games it describes were played. Nothing below had been
measured when the prediction was fixed.

## What is already known

The learning curve peaks at 3,000 self-play games and falls after (+10 Elo
against the hand-written tables at 3,000, −63 at 10,000, −193 at 30,000). The
peak is resolved: 3,000 beats 10,000 by +74 Elo [+43, +105], 4.7σ.

Three of the four hypotheses for the fall are settled without games:

* **Overfitting — not supported.** On 200 human games from the Lichess January
  2013 dump, the scale-free validation measures are flat from 1,000 to 30,000
  games (sign agreement 65.1% → 64.3%, correlation 0.252 → 0.281, neither
  resolved). Validation |TD| falls, but only because the value function is
  shrinking; the terminal error, which moves the other way under shrinkage,
  rises monotonically.
* **Divergence — not supported in its classic form.** Weight norms shrink
  rather than grow without bound: L2 9035 → 9002 → 8869 → 8483.
* **A collapse of the value scale — confirmed.** Every piece decays toward
  zero, fastest for the lightest: pawn 100 → 57.9 by 30,000 games, queen
  900 → 882.6.

Retraining at a fifth of the learning rate does not remove the collapse. Plotted
against the product **learning rate × games**, the two arms lie on one curve:

| lr × games | pawn drop | arm |
|---|---|---|
| 8k | −3.3 | lr 8, 1,000 games |
| 24k | −6.4 | lr 8, 3,000 |
| 40k | −10.8 | lr 40, 1,000 |
| 80k | −17.2 | lr 8, 10,000 |
| 120k | −19.8 | lr 40, 3,000 |
| 400k | −35.1 | lr 40, 10,000 |

So the collapse is not a badly chosen step size. It is a bias in the update
that accumulates with total step mass, and a smaller step delays it in
proportion rather than removing it.

## The claim under test

**If the collapse is what costs strength, then strength is a function of
`lr × games`, not of `games`.**

The two arms make this separable. At 10,000 games the low-rate arm has a pawn
value of 82.8 — between the peak arm (80.2 at lr 40, 3,000 games) and nothing
else on the curve. The high-rate arm at the same 10,000 games sits at 64.9 and
measures −63 Elo.

## Prediction, fixed before the run

`lr=8, 10,000 games` played against the hand-written tables, 600 fixed-length
games at 0.2 s per move:

* **Predicted: between −20 and +30 Elo**, near the peak, because its collapse
  state (pawn 82.8) is close to the peak arm's (pawn 80.2) and far from the
  high-rate arm's at the same game count (pawn 64.9).
* **Falsified if it lands below −40 Elo** — that would put strength with the
  game count rather than with the collapse, and the mechanism would be wrong.
* **Also falsified if it lands above +60** — the collapse would then not be the
  operative variable either, since it would beat the peak it is supposed to
  reproduce.

Resolution: 600 games gives a standard error near 14 Elo, so the interval will
be about ±28. That is enough to separate −63 from +10 (73 Elo apart) and not
enough to separate +10 from 0. The question being asked is which of the two
known values it lands on, and 600 games answers that.

## The second number this run owes

The published figure — *"10,000 games closes 38% of the 175 Elo between bare
material counting and the hand-written tables"* — was measured past the peak.
The same quantity at the peak is measured on the same basis: `lr=40, 3,000
games` against **material-only**, 600 fixed-length games at 0.2 s. No
prediction is registered for it; it is a number the earlier report should have
carried and did not.
