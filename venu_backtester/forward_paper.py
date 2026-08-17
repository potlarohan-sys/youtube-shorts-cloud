from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

from cloud_backtest import prices
from fixed_candidate import sigs, candidate_weights

HERE = Path(__file__).resolve().parent
STATE = HERE / 'forward_paper_state.json'
LEDGER = HERE / 'forward_paper_ledger.csv'
START = pd.Timestamp('2026-08-15')
INITIAL_EQUITY = 100000.0
COST_BPS = 10.0


def load_state():
    if STATE.exists():
        s = json.loads(STATE.read_text())
    else:
        s = {}
    s.setdefault('strategy', 'fixed_consistency_candidate_v1')
    s.setdefault('status', 'NOT_STARTED')
    s.setdefault('start_date', None)
    s.setdefault('last_evaluated_date', None)
    s.setdefault('initial_equity', INITIAL_EQUITY)
    s.setdefault('current_equity', INITIAL_EQUITY)
    s.setdefault('peak_equity', INITIAL_EQUITY)
    s.setdefault('max_drawdown', 0.0)
    s.setdefault('rebalance_cycles', 0)
    s.setdefault('live_trading_enabled', False)
    s.setdefault('cash', INITIAL_EQUITY)
    s.setdefault('shares', {})
    s.setdefault('pending_target', None)
    s.setdefault('pending_signal_date', None)
    s.setdefault('daily_equity', [])
    s.setdefault('note', 'Forward paper test only. Never place real broker orders.')
    return s


def month_end_signal_day(idx, d):
    remaining = idx[(idx > d) & (idx.month == d.month) & (idx.year == d.year)]
    return len(remaining) == 0


def append_ledger(rows):
    cols = ['date','ticker','side','price','shares','notional','weight_before','weight_after','reason']
    old = pd.read_csv(LEDGER) if LEDGER.exists() else pd.DataFrame(columns=cols)
    if rows:
        old = pd.concat([old, pd.DataFrame(rows, columns=cols)], ignore_index=True)
    old.to_csv(LEDGER, index=False)


def equity_from_state(state, row):
    eq = float(state['cash'])
    for t, sh in state['shares'].items():
        p = row.get(t, np.nan)
        if pd.notna(p):
            eq += float(sh) * float(p)
    return eq


def execute_target(state, row, target, d):
    eq_before = equity_from_state(state, row)
    current_values = {t: float(sh) * float(row[t]) for t, sh in state['shares'].items() if t in row.index and pd.notna(row[t])}
    current_weights = {t: v / eq_before for t, v in current_values.items()} if eq_before > 0 else {}
    rows = []
    all_tickers = set(current_values) | {t for t, w in target.items() if float(w) > 0}
    for t in sorted(all_tickers):
        p = row.get(t, np.nan)
        if pd.isna(p) or p <= 0:
            continue
        desired = eq_before * float(target.get(t, 0.0))
        current = current_values.get(t, 0.0)
        delta = desired - current
        if abs(delta) < 1.0:
            continue
        side = 'BUY' if delta > 0 else 'SELL'
        notional = abs(delta)
        sh_delta = notional / float(p)
        fee = notional * COST_BPS / 10000.0
        if side == 'BUY':
            affordable = max(0.0, float(state['cash']) - fee)
            notional = min(notional, affordable)
            if notional < 1.0:
                continue
            sh_delta = notional / float(p)
            state['cash'] = float(state['cash']) - notional - fee
            state['shares'][t] = float(state['shares'].get(t, 0.0)) + sh_delta
        else:
            sh_delta = min(sh_delta, float(state['shares'].get(t, 0.0)))
            notional = sh_delta * float(p)
            fee = notional * COST_BPS / 10000.0
            state['cash'] = float(state['cash']) + notional - fee
            state['shares'][t] = float(state['shares'].get(t, 0.0)) - sh_delta
            if state['shares'][t] <= 1e-10:
                state['shares'].pop(t, None)
        rows.append({
            'date': d.date().isoformat(), 'ticker': t, 'side': side, 'price': float(p),
            'shares': float(sh_delta), 'notional': float(notional),
            'weight_before': float(current_weights.get(t, 0.0)), 'weight_after': float(target.get(t, 0.0)),
            'reason': 'execute_prior_close_signal'
        })
    return rows


def main():
    state = load_state()
    px = prices()
    px = px.loc[(px.index >= START) & px['SPY'].notna()].copy()
    if px.empty:
        print('No forward market close available yet.')
        STATE.write_text(json.dumps(state, indent=2))
        return
    s = sigs(pd.read_csv(HERE/'prices.csv', index_col=0, parse_dates=True).sort_index())
    full_px = pd.read_csv(HERE/'prices.csv', index_col=0, parse_dates=True).sort_index()
    last_done = pd.Timestamp(state['last_evaluated_date']) if state['last_evaluated_date'] else None
    todo = px.index if last_done is None else px.index[px.index > last_done]
    ledger_rows = []
    for d in todo:
        row = full_px.loc[d]
        if state['start_date'] is None:
            state['start_date'] = d.date().isoformat()
            state['status'] = 'RUNNING'
        if state.get('pending_target') is not None:
            target = pd.Series(state['pending_target'], dtype=float).reindex(full_px.columns).fillna(0.0)
            ledger_rows.extend(execute_target(state, row, target, d))
            state['pending_target'] = None
            state['pending_signal_date'] = None
            state['rebalance_cycles'] = int(state['rebalance_cycles']) + 1
        eq = equity_from_state(state, row)
        state['current_equity'] = float(eq)
        state['peak_equity'] = max(float(state['peak_equity']), float(eq))
        dd = float(eq) / float(state['peak_equity']) - 1.0 if state['peak_equity'] else 0.0
        state['max_drawdown'] = min(float(state['max_drawdown']), dd)
        state['daily_equity'].append({'date': d.date().isoformat(), 'equity': float(eq)})
        if month_end_signal_day(full_px.index, d) or state['rebalance_cycles'] == 0:
            target = candidate_weights(full_px, s, d)
            state['pending_target'] = {k: float(v) for k, v in target[target > 0].items()}
            state['pending_signal_date'] = d.date().isoformat()
        state['last_evaluated_date'] = d.date().isoformat()
    append_ledger(ledger_rows)
    STATE.write_text(json.dumps(state, indent=2))
    print(json.dumps({k: state[k] for k in ['status','start_date','last_evaluated_date','current_equity','max_drawdown','rebalance_cycles','pending_signal_date','live_trading_enabled']}, indent=2))

if __name__ == '__main__':
    main()
