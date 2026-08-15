from __future__ import annotations
import json, time
from pathlib import Path
import numpy as np
import pandas as pd
import requests

HERE=Path(__file__).resolve().parent
START='2018-01-01'
TICKERS=['CMG','MU','TRUMP-USD','SNAP','CVS','PYPL','ROKU','DIS','DOT-USD','LYFT','CEG','T','DDOG','OXY','IEO','SLV','GLD','UNH','BAC','HII','NTLA','BA','WFC','TSLA','W','VZ','SPHD','KO','PG','UBER','GOOG','AAPL','NFLX','WYNN','PAPR','DJT','COST','SPYM','QQQM','JPM','VOO','SPY','NVDA','MSFT','WMT','DASH','SOXQ','VUG','BRK-B','ABNB','Q','SOUN','LMND','JETS','GS','CHWY','SOFI','AMZN','WIT','META','ACN','IBM','CRWV','SPGI','LUV','UAL','DEFT','TSM','RCL','WGS','FDX','INTC','AAL','DAL','FISV','Z','NCLH','JBLU','CRM','PLTR','INFY','FRMI','INTU','CRWD','HOOD','GDDY','CRCL','DUOL','PSFE']
UA={'User-Agent':'Mozilla/5.0 VenuHybridCloud/1.1'}

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
    px=pd.DataFrame(data).sort_index(); px.to_csv(HERE/'prices.csv'); return px

def cs_pct(df): return df.rank(axis=1,pct=True).clip(0,1)

def build_scores(px):
    ma50=px.rolling(50,min_periods=40).mean(); ma200=px.rolling(200,min_periods=160).mean()
    m63=px.pct_change(63); m126=px.pct_change(126)
    rel3=m63.sub(m63['SPY'],axis=0); rel6=m126.sub(m126['SPY'],axis=0)
    trend=((px>ma200)*4+(ma50>ma200)*4+cs_pct(rel3)*7+cs_pct(rel6)*6+cs_pct(px.pct_change(20))*4).clip(0,25)
    hi=px.rolling(252,min_periods=60).max(); dd=px/hi-1
    intact=((px>ma200*.90)|(ma50>ma200)).astype(float)
    contra=((-dd/.30).clip(0,1)*intact*15).clip(0,15)
    spy=px['SPY']; spy200=spy.rolling(200,min_periods=160).mean(); spyhi=spy.rolling(252,min_periods=60).max(); spydd=spy/spyhi-1
    reg=pd.Series(9.0,index=px.index)
    reg[(spy<spy200)&(spydd>-0.10)]=7; reg[(spy<spy200)&(spydd<=-0.10)]=11; reg[spydd<=-0.20]=14; reg[spy>spy200*1.12]=5
    risk=pd.DataFrame({c:reg for c in px.columns})
    vol=px.pct_change(fill_method=None).rolling(20).std()*np.sqrt(252)
    # Normalize only active price/risk components to 0-100 for this infrastructure baseline.
    score=((trend+contra+risk)/55.0*100.0).clip(0,100).shift(1)
    return score,vol.shift(1)

def target(srow,vrow,entry=65,maxpos=20):
    e=srow[srow>=entry].sort_values(ascending=False).head(maxpos); w=pd.Series(0.0,index=srow.index)
    for t,s in e.items():
        base=.04 if s>=85 else .03 if s>=75 else .02 if s>=65 else .01
        v=vrow.get(t,np.nan); mult=.5 if pd.notna(v) and v>.70 else .75 if pd.notna(v) and v>.45 else 1
        w[t]=base*mult
    if w.sum()>1: w/=w.sum()
    return w

def simulate(px,scores,vol,start,end,entry,maxpos):
    idx=px.loc[start:end].index; dr=px.pct_change(fill_method=None).fillna(0); rebal=set()
    for d in px.loc[start:end].resample('W-FRI').last().index:
        p=idx.searchsorted(d,side='right')-1
        if p>=0: rebal.add(idx[p])
    cur=pd.Series(0.0,index=px.columns); prev=cur.copy(); out=[]; cost=.0013
    for i,d in enumerate(idx):
        tc=0
        if d in rebal:
            nw=target(scores.loc[d],vol.loc[d],entry,maxpos); tc=(nw-cur).abs().sum()*cost; cur=nw
        out.append(0.0 if i==0 else float((prev*dr.loc[d]).sum()-tc)); prev=cur.copy()
    return pd.Series(out,index=idx)

def perf(r):
    r=r.dropna();
    if len(r)<2: return {}
    eq=(1+r).cumprod(); yrs=len(r)/252; vol=r.std()*np.sqrt(252); dd=eq/eq.cummax()-1
    return {'CAGR':eq.iloc[-1]**(1/yrs)-1,'AnnVol':vol,'Sharpe':r.mean()/r.std()*np.sqrt(252) if r.std()>0 else np.nan,'MaxDrawdown':dd.min(),'TotalReturn':eq.iloc[-1]-1}

def main():
    px=prices()
    if 'SPY' not in px or 'QQQ' not in px: raise SystemExit('SPY/QQQ unavailable')
    scores,vol=build_scores(px); full=simulate(px,scores,vol,px.index.min(),px.index.max(),65,20)
    dr=px.pct_change(fill_method=None).fillna(0)
    bench={'Strategy':full,'SPY':dr['SPY'].reindex(full.index).fillna(0),'QQQ':dr['QQQ'].reindex(full.index).fillna(0)}
    valid=[c for c in TICKERS if c in dr.columns]; bench['EqualWeightWatchlist']=dr[valid].mean(axis=1,skipna=True).reindex(full.index).fillna(0)
    metrics=pd.DataFrame({k:perf(v) for k,v in bench.items()}); metrics.to_csv(HERE/'metrics.csv')
    rows=[]; stitched=[]; cur=px.index.min().normalize(); end=px.index.max().normalize()
    while True:
        tr_end=cur+pd.DateOffset(years=3)-pd.Timedelta(days=1); te_start=tr_end+pd.Timedelta(days=1); te_end=te_start+pd.DateOffset(years=1)-pd.Timedelta(days=1)
        if te_start>end: break
        best=None
        for e in [55,60,65,70,75]:
            for m in [10,15,20,25]:
                r=simulate(px,scores,vol,cur,min(tr_end,end),e,m); sh=r.mean()/r.std()*np.sqrt(252) if r.std()>0 and len(r)>30 else -999
                if best is None or sh>best[0]: best=(sh,e,m)
        test=simulate(px,scores,vol,te_start,min(te_end,end),best[1],best[2]); stitched.append(test)
        p=perf(test); rows.append({'train_start':cur.date(),'train_end':min(tr_end,end).date(),'test_start':te_start.date(),'test_end':min(te_end,end).date(),'train_sharpe':best[0],'entry':best[1],'max_positions':best[2],'test_sharpe':p.get('Sharpe'),'test_return':p.get('TotalReturn')})
        if te_end>=end: break
        cur+=pd.DateOffset(years=1)
    wf=pd.DataFrame(rows); wf.to_csv(HERE/'walk_forward_results.csv',index=False)
    oos=pd.concat(stitched).sort_index(); oos=oos[~oos.index.duplicated()]; oos.to_csv(HERE/'oos_returns.csv',header=['strategy_return'])
    summary={'price_symbols_available':len(px.columns),'watchlist_size':len(TICKERS),'baseline_metrics':metrics.to_dict(),'oos':perf(oos),'note':'Price/risk infrastructure baseline only. Fundamental and veteran-investor overlays are not active yet.'}
    (HERE/'summary.json').write_text(json.dumps(summary,indent=2,default=str)); print(metrics); print('\nWalk-forward\n',wf); print('\nOOS',perf(oos))

if __name__=='__main__': main()
