# Candidate C — Late-Day 0DTE Put Scalp (inferred from uploaded example)

Status: EXPERIMENTAL_FORWARD_PAPER_ONLY

This candidate is separate from Candidate A and Candidate B and must never change their rules.

## What is directly observable in the uploaded example
- Instrument shown: SPXW put, same-day expiration (0DTE)
- Example strike: 7685 put expiring 2026-08-26
- Order submitted/fill time shown: about 3:50 PM ET on 2026-08-26
- Example fill: about $1.50 per contract (~$150 premium plus fees)
- The subsequent chart shows a sharp late-session bearish move in the underlying and a large rise in the put premium.
- The video appears to use a very short-term late-day bearish breakdown/rejection setup. The exact verbal rule set is not fully visible in the clip, so the test below is an explicit mechanical research interpretation, not a claim that it exactly reproduces the creator's method.

## Universe adaptation
The original example uses SPXW, which is outside the user's restricted watchlist. To keep the experiment inside the existing watchlist, Candidate C v1 uses SPY only, the closest listed proxy in the watchlist. Do not trade or paper-trade SPX/SPXW in this candidate unless the user later explicitly expands the universe.

## Mechanical test rules
1. Instrument: SPY 0DTE puts only, when a same-day expiration exists and the option chain is liquid.
2. Evaluation window: 3:45–3:52 PM America/New_York on regular market days. No entry after 3:52 PM.
3. Underlying timeframe: 1-minute SPY bars.
4. Bearish setup requirement: all of the following must be true at evaluation time:
   - SPY is below its 9-EMA and 20-EMA on the 1-minute chart;
   - 9-EMA is below 20-EMA;
   - price has broken below the lowest low of the prior 10 completed 1-minute bars by at least 0.05%;
   - the current 5-minute return is negative;
   - no entry if the current 1-minute bar is already more than 0.35% below the 20-EMA, to avoid chasing an exhausted move.
5. Contract: nearest-to-the-money put, preferring 0 to 1 strike ITM. Require a usable bid/ask and open interest/volume sufficient for a realistic fill.
6. Entry pricing: conservative natural-side assumption; use the ask or worse, never an optimistic midpoint.
7. Premium-at-risk cap: one contract maximum and no more than $200 debit. If the nearest qualifying contract costs more than $200, no trade.
8. One new Candidate C trade maximum per day. Never average down.
9. Exit: first of:
   - option value reaches 3.0x entry debit (+200%);
   - option value falls to 0.5x entry debit (-50%);
   - SPY closes back above the 20-EMA on a completed 1-minute bar after entry;
   - 3:58 PM ET hard exit.
10. Exit pricing: conservative executable bid, not midpoint.
11. No overnight holding, no exercise/assignment exposure, no live orders.

## Evaluation standard
This is a high-variance 0DTE strategy. Do not promote based on a few large winners. Require at least 30 completed paper trades and at least 90 calendar days. Track win rate, median trade, average win/loss, expectancy, profit factor, max drawdown, largest loss, slippage sensitivity, and return on premium at risk. A result dominated by one or two extreme winners should fail robustness review.
