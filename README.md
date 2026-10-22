# Claim Settlement: Settlement-Time Prediction Under Collider Selection in Rust

An insurance claims desk needs a predicted settlement time for every claim in this month's book so it can set reserves. The agent gets `history.dat` (claims the desk has already settled, with the days each one took and the route by which it reached the desk), `batch.dat` (the book to price, with no outcome), and a data dictionary. It must write a Rust program with no dependencies, offline and standard library only, that fits a model at run time and writes `/app/out/predictions.dat` with `claim_id settle_days` for every claim in the batch.

## What makes it hard

The trap is selection on a collider. Settled claims arrive by one of two routes:

- `review`: the standing rule pulled the claim because its amount is over the escalation line OR the intake handler asked for a second look. The handler's judgement is recorded in no column.
- `spot_check`: a random quality-audit sample, worked regardless of amount, paperwork or anything the handler thought.

Because review is triggered by either of two causes, conditioning on it links amount to the hidden judgement inside the reviewed cohort. Among reviewed claims, a large amount is evidence the handler did not flag the claim. The amount coefficient absorbs the missing judgement and comes out at 6.61 where the book's true figure is 4.00.

The wrong cohort is also the big one: 4572 reviewed claims against 600 spot checks. Any validation built at scale on the reviewed file makes the wrong answer look better. On a held-out half of it, the biased fit scores 0.6992 and the clean fit 0.3598. On the actual book being priced:

| Route | R2 on book |
|---|---|
| Fit reviewed cohort | -0.0581 |
| Pool both cohorts | 0.1988 |
| Fit spot checks only (reference) | 0.4162 |
| Down-weight reviewed rows | 0.4380 |

The bar is 0.30: 0.10 above the best route that ignores the split, and 0.12 below the weakest route that respects it. There is no contaminated column, and extra capacity or feature engineering inherits whichever cohort it was fitted on. The model is ordinary least squares on two features with a hand-written 3x3 solve, about a hundred lines of Rust. The difficulty is entirely in choosing the cohort.

## How it's graded

The verifier runs in a separate, offline container. It discards whatever is on disk, restores the crate from a root-owned pristine copy of the collected sources, and runs `cargo clean` and a release build itself. It only ever builds from source and never runs a binary handed over by the agent. The program is then run twice: on the shipped book, and on a second book from a different desk that is baked in at `/opt/holdout` and never reachable by the agent. Twelve checks:

- the shipped export is byte-identical (sha256)
- for both runs: header and exactly two fields per row, one row per claim with duplicates rejected, finite and positive values, and a spread of more than 5 days between the longest and shortest quote
- R2 >= 0.30 on the shipped book and >= 0.25 on the holdout book
- the two runs produce different outputs

The holdout book has a different underlying relationship, so shipped coefficients pasted into the source score -2.835 there. Agent code is built and run as an unprivileged user (`setpriv`, no-new-privs, groups cleared) in its own session, which is torn down afterwards. `/tests` and `/logs/verifier` are closed to that user, and the run scores 0 if either is still reachable. Output is staged only if it is a regular file, reads use `O_NOFOLLOW`, and pytest runs with `-P`.

## Repository layout

- `instruction.md` - the task prompt given to the agent
- `task.toml` - metadata, limits, and the difficulty, solution and verification write-ups
- `environment/` - agent container: `Dockerfile`, `data/` (history.dat, batch.dat, data dictionary), `predictor/` (dependency-free Cargo project with stub `main.rs`)
- `solution/` - `solve.sh`, reference `main.rs`, `generate_data.py` (regenerates the shipped book byte for byte), `generate_holdout.py` (produces the second book)
- `tests/` - verifier `Dockerfile`, `test.sh`, `test_outputs.py`, `skeleton/` crate, `golden/` truth for the shipped book, `holdout/` second book and truth

## Running it

Requires Docker and Harbor (`uv tool install harbor` or `pip install harbor`). From the repo root:

```
harbor run -p . -a oracle
```

runs the reference solution through the verifier (should score reward 1). To try an agent:

```
harbor run -p . -a <agent> -m <model>
```

for example `-a claude-code`.

---

Task design, data generators, reference solution and verifier by Audrey Pope.
