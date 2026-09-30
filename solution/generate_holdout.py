"""The hidden second book the verifier re-runs the agent's binary against.

A different draw AND a different settlement relationship. A different seed alone is not enough: a
program that never opened history.dat and carried the shipped coefficients in its source would
read the same relationship off itself and pass. Under a different intercept and different
coefficients that same program scores far below zero, while one that refits from whatever is in
/app/data reads the new relationship off it and clears the bar as before.

The review rule and the spot-check programme are deliberately unchanged, so the cohort choice is
still exactly what the holdout run tests.

Usage: python solution/generate_holdout.py <seed>
"""
import hashlib
import pathlib
import sys

import generate_data as G

SHIPPED_SEED = 0
# A different desk: slower baseline, a flatter amount response, paperwork that matters more, and a
# handler judgement that weighs slightly less. None of it is inferable from the shipped book.
HOLD = {"B0": 34.0, "B_AMT": 2.5, "B_DOC": -4.5, "B_HANDLER": 4.0}

seed = int(sys.argv[1])
if seed == SHIPPED_SEED:
    sys.exit(f"seed {seed} is the shipped export; the holdout must differ")

for k, v in HOLD.items():
    setattr(G, k, v)

hist, batch = G.build(seed)
out = pathlib.Path(__file__).resolve().parent.parent / "tests" / "holdout"
out.mkdir(parents=True, exist_ok=True)

n = len(hist["days"])
rows = [f"C{i:05d} {hist['amount'][i]:.4f} {hist['doc'][i]:.4f} "
        f"{hist['route'][i]} {hist['days'][i]:.3f}" for i in range(n)]
G.write(out / "history.dat",
        ["claim_id", "amount_z", "doc_score_z", "review_route", "settle_days"], rows, n)
m = len(batch["days"])
G.write(out / "batch.dat", ["claim_id", "amount_z", "doc_score_z"],
        [f"Q{i:05d} {batch['amount'][i]:.4f} {batch['doc'][i]:.4f}" for i in range(m)], m)
with open(out / "batch_truth.dat", "w") as fh:
    fh.write("claim_id settle_days\n")
    fh.write("\n".join(f"Q{i:05d} {batch['days'][i]:.3f}" for i in range(m)) + "\n")

print(f"holdout seed {seed} -> {out}")
for f in ("history.dat", "batch.dat", "batch_truth.dat"):
    b = (out / f).read_bytes()
    print(f"  {f:18s} {len(b):>8d} bytes  sha256 {hashlib.sha256(b).hexdigest()}")
