#!/bin/bash

# Verifier entrypoint. Runs in the verifier container, not the agent's, and sees only the paths
# declared in `artifacts`. All tooling is baked into tests/Dockerfile; nothing is fetched here.

set -uo pipefail

mkdir -p /logs/verifier
echo 0 > /logs/verifier/reward.txt

# Only stdout survives into the feedback bundle, so a script that dies on stderr dies invisibly.
exec 2>&1

chown -R runner:runner /app/predictor /app/out 2>/dev/null || true

as_runner() {
  setpriv --clear-groups --no-new-privs --reuid runner --regid runner "$@"
}

# Close the verifier's own code and the answer keys to the build user before anything untrusted
# runs. /logs/verifier is closed for the same reason: agent code has no business creating files
# beside the reward, even though root's final write would win.
chmod 700 /tests 2>/dev/null || true
chmod 700 /logs/verifier 2>/dev/null || true
if as_runner bash -c 'test -r /tests/test_outputs.py || test -r /opt/golden/batch_truth.dat' \
     2>/dev/null; then
  echo "FATAL: /tests or the answer key is still reachable by the unprivileged build user, so"
  echo "agent-authored code could read the truth it is being graded against. Not grading."
  echo 0 > /logs/verifier/reward.txt
  exit 0
fi
echo "verifier files closed to the unprivileged build user"

# Keep the agent's export exactly as collected. It is restored at the end so the sha256 check
# tests what the agent left rather than what this script swapped in.
rm -rf /opt/agent_data
cp -a /app/data /opt/agent_data
chown -R root:root /opt/agent_data
chmod -R go-rwx /opt/agent_data

# A pristine root-owned copy of the crate as collected. Every run below starts from this rather
# than from whatever the previous run left, so a build script cannot stash state in target/ for a
# later run to read back.
rm -rf /opt/crate_pristine
cp -a /app/predictor /opt/crate_pristine
chown -R root:root /opt/crate_pristine

# $1 = destination for this run's predictions.
#
# The graded numbers come from a binary this script builds from the agent's collected sources with
# a fixed command, not from anything the agent runs itself. Harbor uploads sources with whatever
# mtime they carried, and cargo decides freshness by mtime, so the sources are stamped to now and
# the crate is cleaned first; otherwise an older source counts as already built and the stale
# binary is graded.
run_once() {
  local out="$1" pid
  rm -rf /app/predictor
  cp -a /opt/crate_pristine /app/predictor
  chown -R runner:runner /app/predictor
  find /app/predictor/src -type f -exec touch {} + 2>/dev/null || true
  rm -rf /app/out
  mkdir -p /app/out
  chown runner:runner /app/out

  setsid \
    setpriv --clear-groups --no-new-privs --reuid runner --regid runner \
    bash -c 'cd /app/predictor && cargo clean --release -p claim_predictor 2>/dev/null; \
             cargo run --release --offline --locked' &
  pid=$!
  wait "$pid"
  echo "build-and-run exit status: $?"
  # setsid makes the child a session leader, so its process group id is its own pid and can be
  # addressed directly. Reading the group out of /proc instead races setsid and has taken down
  # the verifier itself on sibling tasks.
  kill -TERM -- -"$pid" 2>/dev/null || true
  kill -KILL -- -"$pid" 2>/dev/null || true
  as_runner bash -c 'kill -9 -1' 2>/dev/null || true

  # Only a regular file is staged. The build runs unprivileged and cannot read the answer key,
  # but it could drop a symlink at this path pointing into /opt/golden, and a plain move would
  # preserve it for root-run pytest to dereference.
  if [ -L /app/out/predictions.dat ] || [ ! -f /app/out/predictions.dat ]; then
    echo "no regular predictions.dat was produced (absent, or not a regular file)"
    rm -f /app/out/predictions.dat
  else
    mv /app/out/predictions.dat "$out"
    chown root:root "$out" 2>/dev/null || true
    chmod 600 "$out" 2>/dev/null || true
  fi
}

set_data() {   # $1 = history source, $2 = batch source
  rm -rf /app/data
  mkdir -p /app/data
  cp -f "$1" /app/data/history.dat
  cp -f "$2" /app/data/batch.dat
  chown -R root:root /app/data
  chmod 444 /app/data/*.dat
  chmod 555 /app/data
}

echo "=== the book that shipped in the agent's image ==="
set_data /opt/agent_data/history.dat /opt/agent_data/batch.dat
run_once /opt/run_batch.dat

# Then a book the agent has never seen, from a different desk under a different settlement
# relationship. Everything above grades the export inside the agent's image, so a program could
# fit once and write the coefficients into its source; this run reads a different relationship
# off a different history.dat and a stored fit scores far below zero on it.
echo "=== a book the agent has never seen ==="
set_data /opt/holdout/history.dat /opt/holdout/batch.dat
run_once /opt/run_holdout.dat

# Restore the agent's export exactly as collected.
rm -rf /app/data
mkdir -p /app/data
cp -a /opt/agent_data/. /app/data/
chmod -R a-w /app/data

as_runner bash -c 'kill -9 -1' 2>/dev/null || true

# -P keeps the working directory off sys.path. The crate runs as runner and writes into /app, so
# without it an /app/pytest.py holding sys.exit(0) would be imported instead of pytest.
python -P -m pytest -o cache_dir=/tmp/pytest_cache \
  --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
if [ "$?" -eq 0 ]; then echo 1 > /logs/verifier/reward.txt; else echo 0 > /logs/verifier/reward.txt; fi

# Harbor grades from reward.txt, never from this script's exit status.
exit 0
