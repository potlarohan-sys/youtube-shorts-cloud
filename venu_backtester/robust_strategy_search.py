from __future__ import annotations
from pathlib import Path
import json, itertools
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
ANN=252
COST=0.0013


def perf(r):
    r=pd.Series(r).dropna()
    if len(r)<30:return {}
    eq=(1+r).cumprod(); yrs=len(r)/ANN; vol=r.std()*np.sqrt(ANN); dd=eq/eq.cummax()-1
    return {'CAGR':eq.iloc[-1]**(1/yrs)-1,'Sharpe':r.mean()/r.std()*np.sqrt(ANN) if r.std()>0 else np.nan,'MaxDD':dd.min(),'TotalReturn':eq.iloc[-1]-1}


def rebalance_dates(idx,start,end):
    s=pd.Series(1,index=idx[(idx>=start)&(idx<=end)])
    out=[]
    for d in s.resample('W-FRI').last().index:
        p=s.index.searchsorted(d,side='right')-1
        if p>=0: out.append(s.index[p])
    return set(out)


def signals(px):
    r=px.pct_change(fill_method=None)
    ma50=px.rolling(50,min_periods=40).mean(); ma200=px.rolling(200,min_periods=160).mean()
    mom3=px.pct_change(63); mom6=px.pct_change(126); mom12=px.pct_change(252)
    vol=r.rolling(63).std()*np.sqrt(ANN)
    spy=px['SPY']; spy200=spy.rolling(200,min_periods=160).mean()
    return {'ma50':ma50,'ma200':ma200,'mom3':mom3,'mom6':mom6,'mom12':mom12,'vol':vol,'spy_risk_on':spy>spy200}


def weights_for(name,d,px,sig,n=10):
    cols=[c for c in px.columns if c not in {'SPY','QQQ'}]
    ma50,ma200=sig['ma50'].loc[d],sig['ma200'].loc[d]
    m3,m6,m12=sig['mom3'].loc[d],sig['mom6'].loc[d],sig['mom12'].loc[d]
    vol=sig['vol'].loc[d]
    risk_on=bool(sig['spy_risk_on'].loc[d]) if pd.notna(sig['spy_risk_on'].loc[d]) else False
    w=pd.Series(0.0,index=px.columns)
    if name=='cash_when_bear' and not risk_on:
        return w
    if name in ('momentum6','cash_when_bear'):
        score=m6[cols]
        elig=(px.loc[d,cols]>ma200[cols]) & score.notna()
    elif name=='momentum12':
        score=m12[cols]
        elig=(px.loc[d,cols]>ma200[cols]) & score.notna()
    elif name=='trend_momentum':
        score=(0.45*m3+0.35*m6+0.20*m12)[cols]
        elig=(px.loc[d,cols]>ma200[cols]) & (ma50[cols]>ma200[cols]) & score.notna()
    elif name=='lowvol_momentum':
        ranks_m=m6[cols].rank(pct=True)
        ranks_v=(-vol[cols]).rank(pct=True)
        score=.65*ranks_m+.35*ranks_v
        elig=(px.loc[d,cols]>ma200[cols]) & score.notna()
    elif name=='risk_adjusted_momentum':
        score=(m6[cols]/vol[cols].replace(0,np.nan))
        elig=(px.loc[d,cols]>ma200[cols]) & score.notna()
    else:
        raise ValueError(name)
    pick=score[elig].nlargest(n).index
    if len(pick)==0:return w
    if name in ('lowvol_momentum','risk_adjusted_momentum'):
        inv=1/vol[pick].replace(0,np.nan)
        ww=inv/inv.sum()
        ww=ww.clip(upper=.15); ww=ww/ww.sum() if ww.sum()>0 else ww
        w[pick]=ww
    else:
        w[pick]=1/len(pick)
    # total gross cap 100%; no leverage
    return w.fillna(0)


def simulate(px,sig,name,start,end,n=10):
    idx=px.loc[start:end].index
    dr=px.pct_change(fill_method=None).fillna(0)
    rb=rebalance_dates(px.index,start,end)
    cur=pd.Series(0.0,index=px.columns); prev=cur.copy(); out=[]
    for i,d in enumerate(idx):
        tc=0
        if d in rb:
            nw=weights_for(name,d,px,sig,n)
            tc=(nw-cur).abs().sum()*COST
            cur=nw
        out.append(0.0 if i==0 else float((prev*dr.loc[d]).sum()-tc))
        prev=cur.copy()
    return pd.Series(out,index=idx)


def split_windows(idx,train_y=3,test_y=1):
    cur=idx.min().normalize(); end=idx.max().normalize(); rows=[]
    while True:
        tr_e=cur+pd.DateOffset(years=train_y)-pd.Timedelta(days=1); te_s=tr_e+pd.Timedelta(days=1); te_e=te_s+pd.DateOffset(years=test_y)-pd.Timedelta(days=1)
        if te_s>end:break
        rows.append((cur,min(tr_e,end),te_s,min(te_e,end)))
        if te_e>=end:break
        cur+=pd.DateOffset(years=1)
    return rows


def main():
    px=pd.read_csv(HERE/'prices.csv',index_col=0,parse_dates=True).sort_index()
    sig=signals(px)
    families=['momentum6','momentum12','trend_momentum','lowvol_momentum','risk_adjusted_momentum','cash_when_bear']
    ns=[5,10,15,20]
    windows=split_windows(px.index)
    all_oos={}
    rows=[]
    for fam in families:
        stitched=[]; wins=[]
        for tr_s,tr_e,te_s,te_e in windows:
            best=None
            for n in ns:
                rr=simulate(px,sig,fam,tr_s,tr_e,n)
                p=perf(rr); sh=p.get('Sharpe',-999)
                # penalize severe drawdowns during training
                obj=sh + 0.5*min(0,p.get('MaxDD',0)+.25)
                if best is None or obj>best[0]:best=(obj,n,p)
            test=simulate(px,sig,fam,te_s,te_e,best[1]); tp=perf(test); stitched.append(test)
            wins.append(tp.get('TotalReturn',np.nan)>0)
            rows.append({'family':fam,'test_start':te_s.date(),'test_end':te_e.date(),'chosen_n':best[1],'train_sharpe':best[2].get('Sharpe'),'train_maxdd':best[2].get('MaxDD'),'test_cagr':tp.get('CAGR'),'test_sharpe':tp.get('Sharpe'),'test_maxdd':tp.get('MaxDD'),'test_return':tp.get('TotalReturn')})
        o=pd.concat(stitched).sort_index(); o=o[~o.index.duplicated()]; all_oos[fam]=o
    wf=pd.DataFrame(rows); wf.to_csv(HERE/'strategy_family_windows.csv',index=False)
    summary=[]
    for fam,o in all_oos.items():
        p=perf(o); f=wf[wf.family==fam]
        summary.append({'family':fam,**p,'positive_window_fraction':(f.test_return>0).mean(),'median_window_sharpe':f.test_sharpe.median(),'worst_window_return':f.test_return.min()})
    # Equal-weight ensemble of all families; diversified process rather than selecting a winner ex post.
    mat=pd.concat(all_oos,axis=1).fillna(0)
    ens=mat.mean(axis=1); ep=perf(ens)
    # Conservative ensemble only of families with positive TRAIN-independent majority windows is reported separately,
    # but it is not used to claim an unbiased OOS result because selection uses test history.
    stable=[x['family'] for x in summary if x['positive_window_fraction']>=.60 and x['Sharpe']>0]
    stable_ens=pd.concat([all_oos[f] for f in stable],axis=1).mean(axis=1) if stable else pd.Series(dtype=float)
    sp=perf(stable_ens) if len(stable_ens) else {}
    sumdf=pd.DataFrame(summary+[{'family':'ALL_FAMILY_ENSEMBLE',**ep,'positive_window_fraction':np.nan,'median_window_sharpe':np.nan,'worst_window_return':np.nan},{'family':'STABLE_EX_POST_ENSEMBLE',**sp,'positive_window_fraction':np.nan,'median_window_sharpe':np.nan,'worst_window_return':np.nan}])
    sumdf.to_csv(HERE/'strategy_family_summary.csv',index=False)
    pd.DataFrame({'ensemble_oos':ens}).to_csv(HERE/'ensemble_oos_returns.csv')
    result={'families':summary,'all_family_ensemble':ep,'stable_families_ex_post':stable,'stable_ensemble_ex_post':sp,'warning':'Stable-family ensemble is ex-post selected and is diagnostic only, not clean OOS evidence.'}
    (HERE/'strategy_search_summary.json').write_text(json.dumps(result,indent=2,default=str))
    print(sumdf.to_string(index=False))

if __name__=='__main__':main()
