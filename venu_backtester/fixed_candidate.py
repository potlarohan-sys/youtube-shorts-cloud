from __future__ import annotations
from pathlib import Path
import json, math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ANN=252
ETF_SET={'SPY','QQQ','QQQM','VOO','VUG','SPHD','GLD','SLV','IEO','SOXQ','JETS'}


def perf(r):
    r=pd.Series(r).dropna()
    if len(r)<30:return {}
    eq=(1+r).cumprod(); yrs=len(r)/ANN; sd=r.std(); dd=eq/eq.cummax()-1
    return {'CAGR':eq.iloc[-1]**(1/yrs)-1,'Sharpe':r.mean()/sd*np.sqrt(ANN) if sd>0 else np.nan,'MaxDD':dd.min(),'TotalReturn':eq.iloc[-1]-1}

def sigs(px):
    return {'ma200':px.rolling(200,min_periods=160).mean(),'mom6':px.pct_change(126,fill_method=None),'mom12':px.pct_change(252,fill_method=None)}

def top_stocks(px,s,d,n=3):
    cols=[c for c in px.columns if c not in ETF_SET and not c.endswith('-USD')]
    score=.6*s['mom6'].loc[d,cols]+.4*s['mom12'].loc[d,cols]
    good=(px.loc[d,cols]>s['ma200'].loc[d,cols]) & score.notna()
    return list(score[good].nlargest(n).index)

def balanced_weights(px,s,d):
    w=pd.Series(0.0,index=px.columns)
    if px.loc[d,'SPY']>s['ma200'].loc[d,'SPY']:w['SPY']=.45
    if 'QQQ' in px and px.loc[d,'QQQ']>s['ma200'].loc[d,'QQQ']:w['QQQ']=.25
    if 'GLD' in px and px.loc[d,'GLD']>s['ma200'].loc[d,'GLD']:w['GLD']=.15
    picks=top_stocks(px,s,d,3)
    if picks:
        each=min(.08,.15/len(picks)); w[picks]=each
    return w

def rotation_weights(px,s,d):
    w=pd.Series(0.0,index=px.columns)
    etfs=[x for x in ETF_SET if x in px.columns and x not in {'SPY','VOO'}]
    score=.5*s['mom6'].loc[d,etfs]+.5*s['mom12'].loc[d,etfs]
    good=(px.loc[d,etfs]>s['ma200'].loc[d,etfs]) & score.notna()
    picks=list(score[good].nlargest(3).index)
    if picks:w[picks]=.25
    return w

def candidate_weights(px,s,d):
    # Fixed 50/50 blend of two independently defined sub-processes.
    return .5*balanced_weights(px,s,d)+.5*rotation_weights(px,s,d)

def schedule(idx,start,end,freq='M',offset=0):
    idx=idx[(idx>=start)&(idx<=end)]
    ser=pd.Series(np.arange(len(idx)),index=idx)
    if freq=='M': groups=ser.groupby([ser.index.year,ser.index.month])
    elif freq=='2M': groups=ser.groupby([ser.index.year,(ser.index.month-1)//2])
    elif freq=='Q': groups=ser.groupby([ser.index.year,ser.index.quarter])
    else: raise ValueError(freq)
    out=[]
    for _,g in groups:
        pos=max(0,len(g)-1-offset); out.append(g.index[pos])
    return set(out)

def simulate(px,s,start,end,cost=.001,freq='M',offset=0):
    idx=px.loc[start:end].index; dr=px.pct_change(fill_method=None).fillna(0); rb=schedule(px.index,start,end,freq,offset)
    cur=pd.Series(0.0,index=px.columns); prev=cur.copy(); out=[]
    for i,d in enumerate(idx):
        tc=0
        if d in rb:
            nw=candidate_weights(px,s,d); tc=(nw-cur).abs().sum()*cost; cur=nw
        out.append(0 if i==0 else float((prev*dr.loc[d]).sum()-tc)); prev=cur.copy()
    return pd.Series(out,index=idx)

def bootstrap(r,horizon=756,n=3000,block=20,seed=7):
    a=np.asarray(pd.Series(r).dropna(),dtype=float); rng=np.random.default_rng(seed); starts=np.arange(0,len(a)-block+1); vals=[]; dds=[]
    need=math.ceil(horizon/block)
    for _ in range(n):
        samp=np.concatenate([a[i:i+block] for i in rng.choice(starts,size=need)])[:horizon]
        eq=np.cumprod(1+samp); vals.append(eq[-1]-1); dds.append(np.min(eq/np.maximum.accumulate(eq)-1))
    vals=np.array(vals); dds=np.array(dds)
    return {'prob_positive':float((vals>0).mean()),'p05_total_return':float(np.quantile(vals,.05)),'median_total_return':float(np.median(vals)),'p05_maxdd':float(np.quantile(dds,.05))}

def main():
    px=pd.read_csv(HERE/'prices.csv',index_col=0,parse_dates=True).sort_index(); s=sigs(px)
    start=max(pd.Timestamp('2021-01-04'),px.index.min()); end=px.index.max()
    base=simulate(px,s,start,end,.001,'M',0); bp=perf(base)
    roll=(1+base).rolling(252).apply(np.prod,raw=True)-1; roll=roll.dropna()
    rolling={'positive_fraction':float((roll>0).mean()),'worst':float(roll.min()),'median':float(roll.median())}
    stress=[]
    for cost in [0,.001,.0025,.005]:
        for freq in ['M','2M','Q']:
            for offset in [0,3,5]:
                r=simulate(px,s,start,end,cost,freq,offset); p=perf(r); stress.append({'cost':cost,'freq':freq,'offset':offset,**p})
    st=pd.DataFrame(stress); st.to_csv(HERE/'candidate_stress.csv',index=False)
    bs=bootstrap(base)
    gate={
        'base_cagr_ge_12pct':bp.get('CAGR',-9)>=.12,
        'base_sharpe_ge_0_9':bp.get('Sharpe',-9)>=.9,
        'base_maxdd_better_than_20pct':bp.get('MaxDD',-9)>=-.20,
        'rolling_1y_positive_ge_85pct':rolling['positive_fraction']>=.85,
        'worst_rolling_1y_better_than_minus_10pct':rolling['worst']>=-.10,
        'stress_all_cagr_positive':bool((st.CAGR>0).all()),
        'stress_min_sharpe_ge_0_75':float(st.Sharpe.min())>=.75,
        'stress_worst_maxdd_better_than_25pct':float(st.MaxDD.min())>=-.25,
        'bootstrap_3y_positive_ge_95pct':bs['prob_positive']>=.95,
        'bootstrap_3y_p05_return_positive':bs['p05_total_return']>0,
    }
    status='PASS_FOR_PAPER_TRADING_ONLY' if all(gate.values()) else 'REJECT'
    out={'status':status,'base':bp,'rolling_1y':rolling,'bootstrap_3y':bs,'stress_min':{'CAGR':float(st.CAGR.min()),'Sharpe':float(st.Sharpe.min()),'MaxDD':float(st.MaxDD.min())},'stress_median':{'CAGR':float(st.CAGR.median()),'Sharpe':float(st.Sharpe.median()),'MaxDD':float(st.MaxDD.median())},'gate':gate,'warning':'Historical robustness does not guarantee future profit. A pass authorizes paper trading only.'}
    (HERE/'candidate_summary.json').write_text(json.dumps(out,indent=2,default=str))
    pd.DataFrame([{'check':k,'pass':v} for k,v in gate.items()]).to_csv(HERE/'candidate_gate.csv',index=False)
    pd.DataFrame({'candidate_return':base}).to_csv(HERE/'candidate_returns.csv')
    print(json.dumps(out,indent=2,default=str))

if __name__=='__main__':main()
