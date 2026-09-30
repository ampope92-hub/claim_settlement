#!/usr/bin/env bash
set -euo pipefail

# The claims that carry a settlement time are the ones the desk worked, and the desk did not pick
# them at random. A claim is pulled for review when the amount is over the line OR when the intake
# handler asks for a second look, and what the handler saw is in no column. Either trigger alone
# is enough, so inside the reviewed cohort a big amount is evidence the handler did not flag it.
# The amount coefficient there ends up carrying the missing judgement and comes out near 6.6 when
# the book's own figure is near 4.0.
#
# The spot-check programme is the way out. Those claims are drawn at random and worked whatever
# they look like, so nothing about them is tied to the judgement. There are only 600 of them
# against 4572 reviewed, and a held-out split of the reviewed file scores the biased fit near 0.70
# against the clean fit's 0.36, so every check available on the big file argues for the wrong
# cohort. Fitting the spot-check rows scores 0.42 on the book, against -0.06 for the reviewed fit
# and 0.20 for pooling the two.
#
# The model is solution/main.rs, next to this script. Rust is not a shell language and it is not
# going in a heredoc.
install -m 644 "$(dirname "$0")/main.rs" /app/predictor/src/main.rs

cd /app/predictor
cargo run --release --offline --locked
