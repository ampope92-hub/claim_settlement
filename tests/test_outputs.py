"""Verifier for the claims settlement model.

test.sh rebuilds the crate from the agent's collected sources and runs it twice: once on the book
that shipped in its image, once on a book from a different desk that it has never seen. Both runs
are held to the same structural contract, and both are scored against settlement times kept
root-only in this image.

numpy is deliberately absent: the arithmetic here is a mean and two sums, and keeping the verifier
free of a numerics stack means nothing about the reference implementation leaks into the image the
agent's code runs in.
"""

import hashlib
import math
import os
import pathlib

import pytest

BATCH_RUN = pathlib.Path("/opt/run_batch.dat")
HOLDOUT_RUN = pathlib.Path("/opt/run_holdout.dat")
BATCH_TRUTH = pathlib.Path("/opt/golden/batch_truth.dat")
HOLDOUT_TRUTH = pathlib.Path("/opt/holdout/batch_truth.dat")
DATA = pathlib.Path("/app/data")

# Calibrated against every route an implementer can reach, measured on the fixtures that ship.
# Fitting the review cohort -- the one with roughly forty times more rows -- scores -0.058 on the
# book and 0.160 on the second one, because that cohort is selected on a trigger the export does
# not carry. Pooling both cohorts scores 0.199 and 0.349. Fitting the spot-check cohort, which is
# drawn at random and carries no selection, scores 0.416 and 0.509, and down-weighting the review
# rows rather than dropping them does slightly better at 0.438 and 0.527. The bars sit in that
# gap: 0.30 is 0.10 above the best route that ignores the cohort split and 0.12 below the weakest
# route that respects it. instruction.md names both figures, so no graded threshold is hidden.
R2_BAR = 0.30
HOLDOUT_R2_BAR = 0.25

SPREAD_MIN = 5.0

# frozen at task-build time; the shipped export must come back byte-identical
HISTORY_SHA = "0562827427e52d15d16a5818107b6346de47428593daaa97fcd68892b1e4b43f"
BATCH_SHA = "8fee2f74af306f6f6f4646610be29e35001b7948dde3109a032bca82445a1673"

RUNS = [
    pytest.param(BATCH_RUN, BATCH_TRUTH, id="batch"),
    pytest.param(HOLDOUT_RUN, HOLDOUT_TRUTH, id="holdout"),
]


def _open(path, mode="r"):
    """Open without following a final symlink.

    test.sh refuses to stage anything that is not a regular file, so a link pointing at the
    answer key never reaches this module. Opening O_NOFOLLOW here as well means a read cannot be
    redirected even if one did.
    """
    return os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), mode)


def _sha(path):
    with _open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _read(path):
    """Parse a two-column file into {claim_id: value}, rejecting a repeated id.

    One line per claim is what the task asks for, so a repeat is a failure rather than something
    to collapse: keyed straight into a dict, a file quoting one claim twice and another not at all
    would still cover the book and still be scored.
    """
    assert path.exists(), f"{path.name}: the model wrote no predictions for this run"
    with _open(path) as fh:
        lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    assert lines, f"{path.name} is empty"
    rows = {}
    for line in lines[1:]:
        fields = line.split()
        assert len(fields) == 2, (
            f"{path.name}: row {line!r} is not exactly two whitespace-separated fields"
        )
        assert fields[0] not in rows, (
            f"{path.name}: claim {fields[0]!r} is quoted on more than one row"
        )
        try:
            rows[fields[0]] = float(fields[1])
        except ValueError:
            pytest.fail(f"{path.name}: {fields[1]!r} is not a number in row {line!r}")
    return rows


def _header(path):
    with _open(path) as fh:
        return fh.readline().split()


def _r2(pred, truth):
    ids = sorted(truth)
    ys = [truth[i] for i in ids]
    mean = sum(ys) / len(ys)
    ss_tot = sum((v - mean) ** 2 for v in ys)
    assert ss_tot > 0, "the settled times have no variance"
    ss_res = sum((pred[i] - truth[i]) ** 2 for i in ids)
    return 1.0 - ss_res / ss_tot


def test_shipped_export_unmodified():
    """The shipped history.dat and batch.dat come back byte-for-byte as issued."""
    assert _sha(DATA / "history.dat") == HISTORY_SHA, "history.dat was altered"
    assert _sha(DATA / "batch.dat") == BATCH_SHA, "batch.dat was altered"


@pytest.mark.parametrize("run_path,truth_path", RUNS)
def test_header_and_schema(run_path, truth_path):
    """Each run writes the stated header and two columns per row."""
    assert run_path.exists(), f"{run_path.name}: the model wrote no predictions for this run"
    assert _header(run_path) == ["claim_id", "settle_days"], (
        f"header must be 'claim_id settle_days', got {_header(run_path)}"
    )
    _read(run_path)


@pytest.mark.parametrize("run_path,truth_path", RUNS)
def test_covers_every_claim_exactly_once(run_path, truth_path):
    """Each run quotes every claim in the book it was handed, exactly once."""
    pred, truth = _read(run_path), _read(truth_path)
    missing = sorted(set(truth) - set(pred))
    extra = sorted(set(pred) - set(truth))
    assert not missing, f"{len(missing)} claims have no quote, e.g. {missing[:5]}"
    assert not extra, f"{len(extra)} quotes are for claims not in the book, e.g. {extra[:5]}"


@pytest.mark.parametrize("run_path,truth_path", RUNS)
def test_values_are_finite_and_positive(run_path, truth_path):
    """Every quoted settlement time is a finite, positive number of days."""
    for cid, v in _read(run_path).items():
        assert math.isfinite(v), f"settle_days is not finite for claim {cid!r}"
        assert v > 0.0, f"settle_days must be above zero for claim {cid!r}: {v}"


@pytest.mark.parametrize("run_path,truth_path", RUNS)
def test_predictions_not_degenerate(run_path, truth_path):
    """The quotes vary across claims rather than being one number repeated."""
    vals = list(_read(run_path).values())
    spread = max(vals) - min(vals)
    assert spread > SPREAD_MIN, (
        f"settle_days spans only {spread:.3f} days across the book, and these claims differ by "
        f"weeks, so a near-constant quote is not a model"
    )


def test_r2_bar():
    """The model explains at least 0.30 of the variation in the book's real settlement times."""
    score = _r2(_read(BATCH_RUN), _read(BATCH_TRUTH))
    assert score >= R2_BAR, (
        f"R2 on the book is {score:.4f}, below the required {R2_BAR:.2f}. The claims that carry a "
        f"settlement time are the ones the desk worked, and the desk did not pick them at random"
    )


def test_holdout_r2():
    """The same program still explains a book from a desk it has never seen."""
    score = _r2(_read(HOLDOUT_RUN), _read(HOLDOUT_TRUTH))
    assert score >= HOLDOUT_R2_BAR, (
        f"R2 on the unseen book is {score:.4f}, below {HOLDOUT_R2_BAR:.2f}. The same program was "
        f"graded on the shipped book, so either it is emitting numbers fitted to that one rather "
        f"than fitting the files it was handed, or the fit does not carry over"
    )


def test_holdout_output_differs_from_shipped_run():
    """Two different books do not produce the same numbers.

    claim_ids run Q00000.. in both, so a program that writes settlement times baked into its
    source emits an identical file twice. Refitting cannot reproduce that.
    """
    a, b = _read(BATCH_RUN), _read(HOLDOUT_RUN)
    shared = sorted(set(a) & set(b))
    assert shared, "the two runs share no claim ids, so they cannot be compared"
    identical = sum(1 for i in shared if a[i] == b[i])
    assert identical < len(shared) * 0.5, (
        f"{identical} of {len(shared)} claims got identical times on two different books, so the "
        f"numbers are constants in the source rather than a fit to the input"
    )
