from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ANN=252; COST=.0010
STOCK_CAP=.08

ETF_SET={'SPY','QQQ','QQQM','VOO','VUG','SPHD','GLD','SLV','IEO','SOXQ','JETS'}

def perf(r):
    r=pd.Series(r).dropna()
    if len(r)<30:return {}
    eq=(1+r).cumprod(); yrs=len(r)/ANN; sd=r.std(); dd=eq/eq.cummax()-1
    return {'CAGR':eq.iloc[-1]**(1/yrs)-1,'Sharpe':r.mean()/sd*np.sqrt(ANN) if sd>0 else np.nan,'MaxDD':dd.min(),'TotalReturn':eq.iloc[-1]-1,'PositiveMonths':(r.resample('ME').apply(lambda x:(1+x).prod()-1)>0).mean()}

def monthly_dates(idx,start,end):
    s=pd.Series(1,index=idx[(idx>=start)&(idx<=end)])
    out=[]
    for d in s.resample('ME').last().index:
        p=s.index.searchsorted(d,side='right')-1
        if p>=0:out.append(s.index[p])
    return set(out)

def sigs(px):
    return {'ma200':px.rolling(200,min_periods=160).mean(),'mom6':px.pct_change(126),'mom12':px.pct_change(252),'vol':px.pct_change(fill_method=None).rolling(63).std()*np.sqrt(ANN)}

def top_stocks(px,s,d,n=5):
    cols=[c for c in px.columns if c not in ETF_SET and not c.endswith('-USD')]
    score=(.6*s['mom6'].loc[d,cols]+.4*s['mom12'].loc[d,cols])
    good=(px.loc[d,cols]>s['ma200'].loc[d,cols]) & score.notna()
    return list(score[good].nlargest(n).index)

def sat_weights(px,s,d,budget=.30,n=5):
    w=pd.Series(0.0,index=px.columns); picks=top_stocks(px,s,d,n)
    if not picks:return w
    each=min(STOCK_CAP,budget/len(picks))
    w[picks]=each
    return w

def make_w(name,px,s,d):
    w=pd.Series(0.0,index=px.columns)
    spy_on=pd.notna(s['ma200'].loc[d,'SPY']) and px.loc[d,'SPY']>s['ma200'].loc[d,'SPY']
    qqq_on='QQQ' in px.columns and pd.notna(s['ma200'].loc[d,'QQQ']) and px.loc[d,'QQQ']>s['ma200'].loc[d,'QQQ']
    if name=='spy_core_70':
        if spy_on:w['SPY']=.70
        w+=sat_weights(px,s,d,.30,5)
    elif name=='dual_core_60':
        if spy_on:w['SPY']=.35
        if qqq_on:w['QQQ']=.25
        w+=sat_weights(px,s,d,.40,5)
    elif name=='risk_managed_core':
        if spy_on:
            w['SPY']=.50
            if qqq_on:w['QQQ']=.25
            w+=sat_weights(px,s,d,.25,5)
        else:
            # Defensive reserve. GLD is in the user's universe; remainder is cash.
            if 'GLD' in px.columns and pd.notna(px.loc[d,'GLD']):w['GLD']=.35
    elif name=='spy_only_risk_managed':
        if spy_on:w['SPY']=.85
        elif 'GLD' in px.columns:w['GLD']=.35
    elif name=='etf_rotation':
        etfs=[x for x in ETF_SET if x in px.columns and x not in {'SPY','VOO'}]
        score=.5*s['mom6'].loc[d,etfs]+.5*s['mom12'].loc[d,etfs]
        good=(px.loc[d,etfs]>s['ma200'].loc[d,etfs]) & score.notna()
        picks=list(score[good].nlargest(3).index)
        if picks:w[picks]=.25  # max 75%, rest cash
    elif name=='balanced_core':
        # Deliberately simple: broad equity + growth + gold, only when each is above trend.
        if spy_on:w['SPY']=.45
        if qqq_on:w['QQQ']=.25
        if 'GLD' in px.columns and px.loc[d,'GLD']>s['ma200'].loc[d,'GLD']:w['GLD']=.15
        w+=sat_weights(px,s,d,.15,3)
    return w.clip(lower=0)

def simulate(px,s,name,start,end):
    idx=px.loc[start:end].index; dr=px.pct_change(fill_method=None).fillna(0); rb=monthly_dates(px.index,start,end)
    cur=pd.Series(0.0,index=px.columns); prev=cur.copy(); out=[]
    for i,d in enumerate(idx):
        tc=0
        if d in rb:
            nw=make_w(name,px,s,d); tc=(nw-cur).abs().sum()*COST; cur=nw
        out.append(0 if i==0 else float((prev*dr.loc[d]).sum()-tc)); prev=cur.copy()
    return pd.Series(out,index=idx)

def windows(idx):
    cur=idx.min().normalize(); end=idx.max().normalize(); out=[]
    while True:
        tr_e=cur+pd.DateOffset(years=3)-pd.Timedelta(days=1); te_s=tr_e+pd.Timedelta(days=1); te_e=te_s+pd.DateOffset(years=1)-pd.Timedelta(days=1)
        if te_s>end:break
        out.append((cur,min(tr_e,end),te_s,min(te_e,end)))
        if te_e>=end:break
        cur+=pd.DateOffset(years=1)
    return out

def main():
    px=pd.read_csv(HERE/'prices.csv',index_col=0,parse_dates=True).sort_index(); s=sigs(px)
    fams=['spy_core_70','dual_core_60','risk_managed_core','spy_only_risk_managed','etf_rotation','balanced_core']
    rows=[]; all_oos={}
    for f in fams:
        parts=[]
        for tr_s,tr_e,te_s,te_e in windows(px.index):
            # No parameter selection: fixed rules reduce overfit risk.
            test=simulate(px,s,f,te_s,te_e); p=perf(test); parts.append(test)
            rows.append({'family':f,'test_start':te_s.date(),'test_end':te_e.date(),'test_cagr':p.get('CAGR'),'test_sharpe':p.get('Sharpe'),'test_maxdd':p.get('MaxDD'),'test_return':p.get('TotalReturn'),'positive_months':p.get('PositiveMonths')})
        o=pd.concat(parts).sort_index(); o=o[~o.index.duplicated()]; all_oos[f]=o
    wf=pd.DataFrame(rows); wf.to_csv(HERE/'conservative_windows.csv',index=False)
    summ=[]
    for f,o in all_oos.items():
        p=perf(o); q=wf[wf.family==f]
        summ.append({'family':f,**p,'positive_window_fraction':(q.test_return>0).mean(),'median_window_sharpe':q.test_sharpe.median(),'worst_window_return':q.test_return.min(),'worst_window_drawdown':q.test_maxdd.min()})
    # Fixed equal-weight process ensemble, not selected using test performance.
    ens=pd.concat(all_oos,axis=1).mean(axis=1); ep=perf(ens)
    summ.append({'family':'FIXED_CONSERVATIVE_ENSEMBLE',**ep,'positive_window_fraction':np.nan,'median_window_sharpe':np.nan,'worst_window_return':np.nan,'worst_window_drawdown':np.nan})
    out=pd.DataFrame(summ); out.to_csv(HERE/'conservative_summary.csv',index=False)
    pd.DataFrame({'oos_return':ens}).to_csv(HERE/'conservative_ensemble_oos.csv')
    (HERE/'conservative_summary.json').write_text(json.dumps({'strategies':summ,'note':'Fixed rules, monthly rebalance, stock positions capped at 8%; results remain historical and not guaranteed.'},indent=2,default=str))
    print(out.to_string(index=False))
if __name__=='__main__':main()
