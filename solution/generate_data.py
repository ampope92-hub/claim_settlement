"""Claims settlement generator.

The crux is selection on a COLLIDER. A claim goes to the review desk when either the amount is
large or the handler flags it, and the handler's judgement is not a column in any export. Among
reviewed claims the amount and that hidden judgement are therefore negatively associated even
though they are independent across the whole book, so a fit on reviewed claims loads the hidden
driver onto the amount coefficient and comes out badly wrong.

What makes it survive contact with a careful agent is that the wrong cohort is the big one. The
reviewed file is roughly forty times the size of the random spot-check file, and a held-out split
of the reviewed file scores the biased fit around 0.70 while the correct fit scores about 0.32 on
that same split. Every check the agent can run at scale recommends the wrong answer.

The spot-check programme is the way out: those claims are drawn at random from the book, so they
carry no selection at all. They are few, which is what makes an agent reluctant to use them alone.
"""
import hashlib
import pathlib
import sys

import numpy as np

# settle_days = B0 + B_AMT*amount + B_DOC*doc + B_HANDLER*judgement + noise
# The judgement term is deliberately the largest single driver: it is what the reviewed cohort
# ends up absorbing into the amount coefficient, and it is never exported.
B0, B_AMT, B_DOC, B_HANDLER = 20.0, 4.0, -3.0, 5.0
NOISE_SD = 2.0

# The review rule, as the desk actually runs it: either trigger sends a claim to review.
AMOUNT_TRIGGER = 0.8
JUDGEMENT_TRIGGER = -0.8

N_BOOK, N_SPOT, N_BATCH = 12000, 600, 4000


def draw(rng, n):
    amount = rng.normal(0.0, 1.0, n)
    judgement = rng.normal(0.0, 1.0, n)
    doc = rng.normal(0.0, 1.0, n)
    days = (B0 + B_AMT * amount + B_DOC * doc + B_HANDLER * judgement
            + rng.normal(0.0, NOISE_SD, n))
    return amount, doc, judgement, days


def build(seed):
    rng = np.random.default_rng(seed)
    amount, doc, judgement, days = draw(rng, N_BOOK)
    reviewed = (amount > AMOUNT_TRIGGER) | (judgement < JUDGEMENT_TRIGGER)
    spot = np.zeros(N_BOOK, dtype=bool)
    spot[rng.choice(np.where(~reviewed)[0], N_SPOT, replace=False)] = True
    keep = reviewed | spot
    hist = {"amount": amount[keep], "doc": doc[keep], "days": days[keep],
            "route": np.where(reviewed[keep], "review", "spot_check")}
    b_amount, b_doc, _, b_days = draw(rng, N_BATCH)
    batch = {"amount": b_amount, "doc": b_doc, "days": b_days}
    return hist, batch


def write(path, cols, rows, n):
    with open(path, "w") as fh:
        fh.write(" ".join(cols) + "\n")
        fh.write("\n".join(rows) + "\n")


def main():
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    root = pathlib.Path(__file__).resolve().parent.parent
    hist, batch = build(seed)

    n = len(hist["days"])
    rows = [f"C{i:05d} {hist['amount'][i]:.4f} {hist['doc'][i]:.4f} "
            f"{hist['route'][i]} {hist['days'][i]:.3f}" for i in range(n)]
    write(root / "environment/data/history.dat",
          ["claim_id", "amount_z", "doc_score_z", "review_route", "settle_days"], rows, n)

    m = len(batch["days"])
    rows = [f"Q{i:05d} {batch['amount'][i]:.4f} {batch['doc'][i]:.4f}" for i in range(m)]
    write(root / "environment/data/batch.dat",
          ["claim_id", "amount_z", "doc_score_z"], rows, m)

    truth = root / "tests/golden"
    truth.mkdir(parents=True, exist_ok=True)
    with open(truth / "batch_truth.dat", "w") as fh:
        fh.write("claim_id settle_days\n")
        fh.write("\n".join(f"Q{i:05d} {batch['days'][i]:.3f}" for i in range(m)) + "\n")

    reviewed = (hist["route"] == "review").sum()
    print(f"seed {seed}: history {n} rows ({reviewed} review, {n - reviewed} spot_check), "
          f"batch {m}")
    for f in ("environment/data/history.dat", "environment/data/batch.dat",
              "tests/golden/batch_truth.dat"):
        b = (root / f).read_bytes()
        print(f"  {f:36s} {len(b):>8d} bytes  sha256 {hashlib.sha256(b).hexdigest()}")


if __name__ == "__main__":
    main()
