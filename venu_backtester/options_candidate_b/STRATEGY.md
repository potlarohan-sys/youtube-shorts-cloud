# Candidate B — AAPL Bull Call Debit Spread (inferred from uploaded example)

Status: EXPERIMENTAL_FORWARD_PAPER_ONLY

This is a separate candidate and does not modify fixed_consistency_candidate_v1.

## What was observable in the example
- Underlying: AAPL
- Structure: bullish call debit spread
- Example strikes shown: long 307.5 call / short 310 call
- Width: $2.50
- Example debit: about $0.73 ($73/contract)
- Example entry date: 2026-08-13
- Example expiration: 2026-08-21
- Example exit: 2026-08-20 around $2.36 credit, approximately +223%
- Chart rationale shown: double-bottom / bullish reversal confirmation and subsequent upside move

## Testable inferred rules
Because the video shows one successful trade rather than a complete mechanical system, the following rules are an explicit research interpretation, not a claim that these are the creator's exact rules.

1. Universe: AAPL only for v1, because the example is AAPL and this avoids changing multiple variables at once.
2. Setup: detect a recent double-bottom style reversal over the prior 10–30 sessions, with the two local lows within 2% of each other and separated by at least 3 sessions.
3. Confirmation: close above the interim swing high / neckline after the second low, with close above the 20-day moving average.
4. Entry timing: paper entry at the next regular-session close after confirmation; no same-close lookahead.
5. Option structure: bull call debit spread, 7–14 DTE. Long call nearest to spot or slightly OTM; short call $2.50 higher when available.
6. Debit filter: debit must be <= 40% of spread width. Otherwise no trade.
7. Position size: one spread maximum. Paper only.
8. Exit: first of (a) spread value >= 3.0x entry debit (+200%), (b) spread value <= 0.5x entry debit (-50%), (c) one trading day before expiration, or (d) bullish thesis invalidates with AAPL closing below the second-bottom support.
9. Costs/slippage: use conservative mid-to-natural fill assumptions and record quoted bid/ask when available.
10. No live orders. No margin. No averaging down.

## Evaluation
Do not promote from a single winner. Require at least 20 completed paper spreads and at least 90 calendar days before judging. Track win rate, average win/loss, expectancy, profit factor, max drawdown, and return on premium at risk.

The uploaded trade is anecdotal evidence only; this test is designed to determine whether the pattern has repeatable forward value.