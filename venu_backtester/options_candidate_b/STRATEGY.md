# Candidate B — Watchlist Bull Call Debit Spread (inferred from uploaded example)

Status: EXPERIMENTAL_FORWARD_PAPER_ONLY

This is a separate candidate and does not modify fixed_consistency_candidate_v1.

## What was observable in the example
- Example underlying: AAPL
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

1. Universe: scan the user's existing watchlist, but only optionable U.S.-listed common stocks. Exclude ETFs, crypto, metals/commodity proxies, and any symbol without a usable listed-options chain. Watchlist stocks: CMG, MU, SNAP, CVS, PYPL, ROKU, DIS, LYFT, CEG, T, DDOG, OXY, UNH, BAC, HII, NTLA, BA, WFC, TSLA, W, VZ, KO, PG, UBER, GOOG, AAPL, NFLX, WYNN, DJT, COST, JPM, NVDA, MSFT, WMT, DASH, BRK-B, ABNB, SOUN, LMND, GS, CHWY, SOFI, AMZN, WIT, META, ACN, IBM, CRWV, SPGI, LUV, UAL, TSM, RCL, WGS, FDX, INTC, AAL, DAL, FISV, Z, NCLH, JBLU, CRM, PLTR, INFY, FRMI, INTU, CRWD, HOOD, GDDY, CRCL, DUOL, PSFE. Symbols that are invalid, non-optionable, stale, or ambiguous are skipped rather than guessed.
2. Setup: detect a recent double-bottom style reversal over the prior 10–30 sessions, with the two local lows within 2% of each other and separated by at least 3 sessions.
3. Confirmation: close above the interim swing high / neckline after the second low, with close above the 20-day moving average.
4. Entry timing: paper entry at the next regular-session close after confirmation; no same-close lookahead.
5. Candidate ranking: if multiple stocks confirm on the same day, rank by cleanest pattern first: smaller bottom-to-bottom price difference, stronger breakout above neckline, higher relative volume if available, and tighter/liquid option spreads. Open at most one new spread per day and at most three concurrent Candidate B spreads.
6. Option structure: bull call debit spread, 7–14 DTE. Long call nearest to spot or slightly OTM; short call one standard strike increment above, targeting roughly $2.50 width when available. For higher-priced stocks where standard increments differ, use the nearest practical width around 0.5%–1.5% of spot while keeping defined risk.
7. Debit filter: debit must be <= 40% of spread width. Otherwise no trade.
8. Liquidity filter: skip chains with stale quotes, no reliable bid/ask, or obviously unusable spreads. Prefer contracts with meaningful open interest/volume when available.
9. Position size: one spread per signal; at most three concurrent spreads. Paper only.
10. Exit: first of (a) spread value >= 3.0x entry debit (+200%), (b) spread value <= 0.5x entry debit (-50%), (c) one trading day before expiration, or (d) bullish thesis invalidates with the underlying closing below the second-bottom support.
11. Costs/slippage: use conservative executable bid/ask assumptions, not optimistic mids, and record quoted bid/ask when available.
12. No live orders. No margin. No averaging down.

## Evaluation
Do not promote from a single winner. Require at least 20 completed paper spreads and at least 90 calendar days before judging. Track win rate, average win/loss, expectancy, profit factor, max drawdown, and return on premium at risk.

The uploaded AAPL trade is anecdotal evidence only; this test is designed to determine whether the same pattern has repeatable forward value across the user's stock watchlist.