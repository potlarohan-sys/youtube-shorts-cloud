from __future__ import annotations
import json, time
from pathlib import Path
import numpy as np
import pandas as pd
import requests

HERE=Path(__file__).resolve().parent
START='2018-01-01'
TICKERS=['CMG','MU','TRUMP-USD','SNAP','CVS','PYPL','ROKU','DIS','DOT-USD','LYFT','CEG','T','DDOG','OXY','IEO','SLV','GLD','UNH','BAC','HII','NTLA','BA','WFC','TSLA','W','VZ','SPHD','KO','PG','UBER','GOOG','AAPL','NFLX','WYNN','PAPR','DJT','COST','SPYM','QQQM','JPM','VOO','SPY','NVDA','MSFT','WMT','DASH','SOXQ','VUG','BRK-B','ABNB','Q','SOUN','LMND','JETS','GS','CHWY','SOFI','AMZN','WIT','META','ACN','IBM','CRWV','SPGI','LUV','UAL','DEFT','TSM','RCL','WGS','FDX','INTC','AAL','DAL','FISV','Z','NCLH','JBLU','CRM','PLTR','INFY','FRMI','INTU','CRWD','HOOD','GDDY','CRCL','DUOL','PSFE']
UA={'User-Agent':'Mozilla/5.0 VenuHybridCloud/2.0'}
COST=.0013

def unix(x): return int(pd.Timestamp(x,tz='UTC').timestamp())

def fetch_one(t):
    url=f'https://query1.finance.yahoo.com/v8/finance/chart/{t}'
    params={'period1':unix(START),'period2':unix((pd.Timestamp.utcnow()+pd.Timedelta(days=1)).date()),'interval':'1d','events':'div,splits','includeAdjustedClose':'true'}
    last=None
    for k in range(3):
        try:
            r=requests.get(url,params=params,headers=UA,timeout=30); r.raise_for_status()
            o=r.json()['chart']['result'][0]
            idx=pd.to_datetime(o['timestamp'],unit='s',utc=True).tz_convert(None).normalize()
            adj=o['indicators']['adjclose'][0]['adjclose']
            return pd.Series(adj,index=idx,dtype=float,name=t).dropna()
        except Exception as e:
            last=e; time.sleep(1.5*(k+1))
    raise RuntimeError(f'{t}: {last}')

def prices():
    data={}; fails={}
    for i,t in enumerate(dict.fromkeys(TICKERS+['QQQ'])):
        try: data[t]=fetch_one(t); print(f'[{i+1}] OK {t}')
        except Exception as e: fails[t]=str(e); print(f'[{i+1}] FAIL {t}: {e}')
        time.sleep(.08)
    (HERE/'price_failures.json').write_text(json.dumps(fails,indent=2))
    px=pd.DataFrame(data).sort_index()
    if 'SPY' not in px: raise RuntimeError('SPY unavailable')
    px=px.loc[px['SPY'].notna()].copy()
    px.to_csv(HERE/'prices.csv')
    return px

def rank_pct(df): return df.rank(axis=1,pct=True)

def indicators(px):
    r=px.pct_change(fill_method=None)
    ma100=px.rolling(100,min_periods=80).mean(); ma200=px.rolling(200,min_periods=160).mean()
    mom63=px.pct_change(63); mom126=px.pct_change(126); mom252=px.pct_change(252)
    vol63=r.rolling(63,min_periods=40).std()*np.sqrt(252)
    spy=px['SPY']; spy200=spy.rolling(200,min_periods=160).mean()
    spyvol=r['SPY'].rolling(20,min_periods=15).std()*np.sqrt(252)
    return {'r':r,'ma100':ma100,'ma200':ma200,'m63':mom63,'m126':mom126,'m252':mom252,'v63':vol63,'spy200':spy200,'spyvol':spyvol}

def investable(px, date):
    # no crypto; require actual price and >=160 observations so indicators are meaningful
    cols=[c for c in px.columns if not c.endswith('-USD') and c not in {'SPY','QQQ'}]
    return [c for c in cols if pd.notna(px.at[date,c])]

def regime_exposure(px,I,d,mode):
    spy=px.at[d,'SPY']; ma=I['spy200'].at[d]; v=I['spyvol'].at[d]
    if pd.isna(ma): return 0.0
    if mode=='none': return 1.0
    if mode=='binary': return 1.0 if spy>ma else 0.35
    # graduated defensive regime
    exp=1.0 if spy>ma else 0.50
    if pd.notna(v) and v>0.30: exp*=0.65
    elif pd.notna(v) and v>0.22: exp*=0.80
    return float(np.clip(exp,0.20,1.0))

def invvol_weights(cands,volrow,total=1.0,cap=.08):
    if not cands: return pd.Series(dtype=float)
    v=volrow[cands].replace([np.inf,-np.inf],np.nan).clip(lower=.08)
    v=v.dropna()
    if len(v)==0: return pd.Series(dtype=float)
    raw=1/v; w=raw/raw.sum()*total
    # iterative cap redistribution
    for _ in range(5):
        over=w>w.index.map(lambda x: cap)
        if not over.any(): break
        excess=float((w[over]-cap).sum()); w[over]=cap
        under=~over
        if under.any() and excess>0:
            base=w[under]
            if base.sum()>0: w[under]+=excess*base/base.sum()
    if w.sum()>total: w*=total/w.sum()
    return w

def target(px,I,d,name):
    names=investable(px,d)
    if not names: return pd.Series(0.0,index=px.columns)
    m63=I['m63'].loc[d,names]; m126=I['m126'].loc[d,names]; m252=I['m252'].loc[d,names]
    ma100=I['ma100'].loc[d,names]; ma200=I['ma200'].loc[d,names]; p=px.loc[d,names]
    vol=I['v63'].loc[d,names]
    eligible=(p>ma200) & m126.notna()
    score=pd.Series(np.nan,index=names,dtype=float)
    n=15; mode='graduated'; cap=.08
    if name=='RS6_10':
        score=rank_pct(pd.DataFrame([m126],index=[d])).iloc[0]; n=10
    elif name=='DUAL_15':
        score=.55*rank_pct(pd.DataFrame([m126],index=[d])).iloc[0]+.45*rank_pct(pd.DataFrame([m252],index=[d])).iloc[0]; n=15
        eligible &= m252.notna()
    elif name=='FASTSLOW_15':
        score=.35*rank_pct(pd.DataFrame([m63],index=[d])).iloc[0]+.40*rank_pct(pd.DataFrame([m126],index=[d])).iloc[0]+.25*rank_pct(pd.DataFrame([m252],index=[d])).iloc[0]; n=15
        eligible &= m252.notna()
    elif name=='LOWVOL_MOM_15':
        score=.50*rank_pct(pd.DataFrame([m126],index=[d])).iloc[0]+.25*rank_pct(pd.DataFrame([m252],index=[d])).iloc[0]+.25*(1-rank_pct(pd.DataFrame([vol],index=[d])).iloc[0]); n=15
        eligible &= m252.notna()
    elif name=='TREND_DEF_15':
        score=.45*rank_pct(pd.DataFrame([m63],index=[d])).iloc[0]+.35*rank_pct(pd.DataFrame([m126],index=[d])).iloc[0]+.20*(p>ma100).astype(float); n=15; mode='binary'
    elif name=='ENSEMBLE_15':
        score=.25*rank_pct(pd.DataFrame([m63],index=[d])).iloc[0]+.30*rank_pct(pd.DataFrame([m126],index=[d])).iloc[0]+.25*rank_pct(pd.DataFrame([m252],index=[d])).iloc[0]+.10*(p>ma100).astype(float)+.10*(1-rank_pct(pd.DataFrame([vol],index=[d])).iloc[0]); n=15
        eligible &= m252.notna()
    else: raise ValueError(name)
    c=score[eligible].dropna().sort_values(ascending=False).head(n).index.tolist()
    exposure=regime_exposure(px,I,d,mode)
    ww=invvol_weights(c,vol,total=exposure,cap=cap)
    w=pd.Series(0.0,index=px.columns); w.loc[ww.index]=ww.values
    return w

def rebalance_dates(idx,start,end):
    sub=pd.Series(index=idx[(idx>=pd.Timestamp(start))&(idx<=pd.Timestamp(end))],data=1.0)
    # month-end trading day; slower turnover and less noise than weekly
    return set(sub.resample('ME').last().dropna().index)

def simulate(px,I,start,end,name):
    idx=px.loc[start:end].index
    if len(idx)<2: return pd.Series(dtype=float)
    dr=I['r'].fillna(0); reb=rebalance_dates(px.index,start,end)
    cur=pd.Series(0.0,index=px.columns); prev=cur.copy(); out=[]
    for i,d in enumerate(idx):
        tc=0.0
        if d in reb:
            nw=target(px,I,d,name)
            tc=float((nw-cur).abs().sum()*COST); cur=nw
        out.append(0.0 if i==0 else float((prev*dr.loc[d]).sum()-tc)); prev=cur.copy()
    return pd.Series(out,index=idx,name=name)

def perf(r):
    r=pd.Series(r).dropna()
    if len(r)<2:return {}
    eq=(1+r).cumprod(); yrs=len(r)/252; sd=r.std(); dd=eq/eq.cummax()-1
    return {'CAGR':eq.iloc[-1]**(1/yrs)-1,'AnnVol':sd*np.sqrt(252),'Sharpe':r.mean()/sd*np.sqrt(252) if sd>0 else np.nan,'MaxDrawdown':dd.min(),'TotalReturn':eq.iloc[-1]-1,'PositiveDays':float((r>0).mean())}

def train_score(r):
    p=perf(r)
    if not p or pd.isna(p.get('Sharpe')): return -999
    # Reward risk-adjusted return; penalize deep drawdowns to avoid selecting fragile high-beta variants.
    return float(p['Sharpe'] + 0.75*p['CAGR'] - 0.60*abs(p['MaxDrawdown']))

def main():
    px=prices(); I=indicators(px)
    if 'QQQ' not in px: raise RuntimeError('QQQ unavailable')
    candidates=['RS6_10','DUAL_15','FASTSLOW_15','LOWVOL_MOM_15','TREND_DEF_15','ENSEMBLE_15']
    allrets={n:simulate(px,I,px.index.min(),px.index.max(),n) for n in candidates}
    dr=I['r'].fillna(0)
    metrics=pd.DataFrame({n:perf(r) for n,r in allrets.items()})
    metrics['SPY']=pd.Series(perf(dr['SPY'])); metrics['QQQ']=pd.Series(perf(dr['QQQ']))
    valid=[c for c in TICKERS if c in dr.columns and not c.endswith('-USD')]
    metrics['EqualWeightWatchlist']=pd.Series(perf(dr[valid].mean(axis=1,skipna=True)))
    metrics.to_csv(HERE/'metrics.csv')

    rows=[]; stitched=[]; cur=px.index.min().normalize(); end=px.index.max().normalize()
    while True:
        tr_end=cur+pd.DateOffset(years=3)-pd.Timedelta(days=1); te_start=tr_end+pd.Timedelta(days=1); te_end=te_start+pd.DateOffset(years=1)-pd.Timedelta(days=1)
        if te_start>end: break
        choices=[]
        for n in candidates:
            rr=simulate(px,I,cur,min(tr_end,end),n); choices.append((train_score(rr),n,perf(rr)))
        choices.sort(reverse=True,key=lambda x:x[0]); best=choices[0]
        test=simulate(px,I,te_start,min(te_end,end),best[1]); tp=perf(test); stitched.append(test)
        rows.append({'train_start':cur.date(),'train_end':min(tr_end,end).date(),'test_start':te_start.date(),'test_end':min(te_end,end).date(),'chosen_strategy':best[1],'train_selection_score':best[0],'train_sharpe':best[2].get('Sharpe'),'train_cagr':best[2].get('CAGR'),'train_maxdd':best[2].get('MaxDrawdown'),'test_sharpe':tp.get('Sharpe'),'test_cagr':tp.get('CAGR'),'test_return':tp.get('TotalReturn'),'test_maxdd':tp.get('MaxDrawdown')})
        if te_end>=end: break
        cur+=pd.DateOffset(years=1)
    wf=pd.DataFrame(rows); wf.to_csv(HERE/'walk_forward_results.csv',index=False)
    oos=pd.concat(stitched).sort_index(); oos=oos[~oos.index.duplicated(keep='first')]; oos.to_csv(HERE/'oos_returns.csv',header=['strategy_return'])
    op=perf(oos); poswin=float((wf['test_return']>0).mean()) if len(wf) else np.nan
    # Conservative research gate, not a guarantee.
    gate={'oos_cagr_gt_5pct':op.get('CAGR',-9)>.05,'oos_sharpe_gt_0_6':op.get('Sharpe',-9)>.60,'oos_maxdd_better_than_25pct':op.get('MaxDrawdown',-9)>-.25,'positive_test_windows_ge_70pct':poswin>=.70,'at_least_4_test_windows':len(wf)>=4}
    summary={'price_symbols_available':len(px.columns),'watchlist_size':len(TICKERS),'candidate_metrics':metrics.to_dict(),'walk_forward_oos':op,'positive_oos_window_fraction':poswin,'research_gate':gate,'research_gate_pass':bool(all(gate.values())),'note':'Pre-defined monthly-rebalanced momentum/trend/low-volatility family. Candidate chosen on each 3y training window and evaluated on next unseen year. Current-watchlist selection bias remains; no guarantee of future performance.'}
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2,default=str))
    print(metrics); print('\nWALK FORWARD\n',wf.to_string(index=False)); print('\nOOS',op); print('\nGATE',gate,'PASS=',all(gate.values()))

if __name__=='__main__': main()
