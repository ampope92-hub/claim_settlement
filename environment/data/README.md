# Claims desk export, 2026-08-14

Two whitespace-delimited files, one header line each. `history.dat` is settled claims with the
number of days each one took. `batch.dat` is the current month's book, same columns, no outcome.

## Columns

| column | source | description |
|---|---|---|
| `claim_id` | claims register | our reference |
| `amount_z` | claims register | claim amount, standardised against the book |
| `doc_score_z` | intake scan | completeness of the paperwork at intake, standardised |
| `review_route` | desk log | how the claim came to the review desk (history only) |
| `settle_days` | desk log | days from intake to settlement (history only) |

## How a claim reaches the desk

Only claims the desk has actually worked carry a settlement time, so `history.dat` is what the
desk has handled rather than everything that came in. There are two ways onto the desk and
`review_route` records which one applied.

`review` is the standing rule. A claim is pulled for review when the amount is above the
escalation line, or when the intake handler marks it as needing a second pair of eyes. Either
trigger on its own is enough. What the handler was reacting to is not recorded anywhere: it is a
judgement made at intake, written on no form and not in this export.

`spot_check` is the quality programme. A fixed number of claims are drawn from the month's book at
random and worked regardless of amount, paperwork or anything the handler thought, so that the
desk has a sample it did not choose. It is a small programme and it is expensive, which is why the
sample is the size it is.

## The batch

`batch.dat` is every claim opened this month, not a selection from it. We price the whole book
against it, so the number we need is what a claim like this takes in general, not what it took
among the ones we happened to work.
