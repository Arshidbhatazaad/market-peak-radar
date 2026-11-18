import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import StringIO

st.set_page_config(page_title='Market Peak Radar | Institutional Research', page_icon='◈', layout='wide')

# Light institutional visual system
st.markdown('''<style>
:root { --ink:#172b4d; --muted:#62748a; --line:#dce4ee; --paper:#f5f8fc; --blue:#1769aa; }
.stApp { background:#f5f8fc; color:#172b4d; }
[data-testid="stHeader"] { background:rgba(245,248,252,.92); }
[data-testid="stSidebar"] { background:#edf2f8; border-right:1px solid #dce4ee; }
.block-container { padding-top:1.2rem; max-width:1500px; }
[data-testid="stMetric"] { background:#fff; border:1px solid #dce4ee; padding:14px 16px; border-radius:10px; }
[data-testid="stDataFrame"] { background:#fff; }
hr { border-color:#dce4ee; }
.small-note { color:#62748a; font-size:.86rem; }
.section-kicker { color:#1769aa; font-weight:700; letter-spacing:.08em; font-size:.72rem; text-transform:uppercase; }
</style>''', unsafe_allow_html=True)

st.title('◈ MARKET PEAK RADAR')
st.caption('INSTITUTIONAL RESEARCH WORKSPACE  ·  INDIA EQUITIES  ·  FREE DATA EDITION')
st.info('Research platform, not a broker terminal. Market and company data are sourced from Yahoo Finance via yfinance and may be delayed, incomplete or revised. FII/DII, derivatives participant positioning and official filings are **not** silently inferred: upload source files where required. Verify all figures against NSE/BSE, company filings and fund disclosures.')

DEFAULT_TICKERS = ['RELIANCE.NS','TCS.NS','HDFCBANK.NS','INFY.NS','ICICIBANK.NS']
SECTOR_INDICES = {
    'Nifty 50':'^NSEI','Nifty Bank':'^NSEBANK','Nifty IT':'^CNXIT','Nifty Auto':'^CNXAUTO',
    'Nifty Pharma':'^CNXPHARMA','Nifty FMCG':'^CNXFMCG','Nifty Metal':'^CNXMETAL',
    'Nifty Realty':'^CNXREALTY','Nifty PSU Bank':'^CNXPSUBANK','Nifty Energy':'^CNXENERGY'
}

@st.cache_data(ttl=900, show_spinner=False)
def get_history(symbol, period='1y', interval='1d'):
    try:
        df = yf.Ticker(symbol).history(period=period, interval=interval, auto_adjust=True)
        if df is None or df.empty: return pd.DataFrame()
        return df.dropna(how='all')
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def get_fundamentals(symbol):
    t = yf.Ticker(symbol)
    info = {}
    try: info = t.get_info()
    except Exception: pass
    def safe_stmt(attr):
        try:
            d = getattr(t, attr)
            return d if isinstance(d, pd.DataFrame) else pd.DataFrame()
        except Exception: return pd.DataFrame()
    return info, safe_stmt('quarterly_income_stmt'), safe_stmt('income_stmt'), safe_stmt('quarterly_cashflow'), safe_stmt('balance_sheet')

def nval(x):
    try:
        v=float(x)
        return v if np.isfinite(v) else np.nan
    except Exception: return np.nan

def fmt_num(x, suffix=''):
    return '—' if pd.isna(x) else f'{x:,.2f}{suffix}'

def fmt_inr(x):
    if pd.isna(x): return '—'
    x=float(x)
    if abs(x)>=1e12: return f'₹{x/1e12:.2f}T'
    if abs(x)>=1e9: return f'₹{x/1e9:.2f}B'
    if abs(x)>=1e7: return f'₹{x/1e7:.2f}Cr'
    return f'₹{x:,.0f}'

def statement_series(df, candidates):
    if df is None or df.empty: return pd.Series(dtype=float)
    for cand in candidates:
        hits=[idx for idx in df.index if cand.lower() in str(idx).lower()]
        if hits:
            s=pd.to_numeric(df.loc[hits[0]], errors='coerce').dropna()
            try: s.index=pd.to_datetime(s.index)
            except Exception: pass
            return s.sort_index()
    return pd.Series(dtype=float)

def pct(a,b):
    if pd.isna(a) or pd.isna(b) or b==0: return np.nan
    return (a/b-1)*100

def risk_stats(returns):
    r=returns.dropna()
    if len(r)<30: return {'vol':np.nan,'sharpe':np.nan,'maxdd':np.nan}
    vol=r.std()*np.sqrt(252)*100
    sharpe=(r.mean()*252)/(r.std()*np.sqrt(252)) if r.std()!=0 else np.nan
    wealth=(1+r).cumprod(); dd=(wealth/wealth.cummax()-1).min()*100
    return {'vol':vol,'sharpe':sharpe,'maxdd':dd}

with st.sidebar:
    st.markdown('### Research controls')
    raw=st.text_area('Equity universe · Yahoo symbols, one per line','\n'.join(DEFAULT_TICKERS),height=150)
    tickers=list(dict.fromkeys(x.strip().upper() for x in raw.replace(',','\n').splitlines() if x.strip()))
    period=st.selectbox('Market history',['6mo','1y','2y','5y'],index=1)
    benchmark=st.selectbox('Benchmark',['^NSEI','^BSESN'],format_func=lambda x:'Nifty 50' if x=='^NSEI' else 'BSE Sensex')
    refresh=st.button('Refresh data',type='primary',use_container_width=True)
    if refresh: st.cache_data.clear()
    st.caption('Symbols usually use .NS for NSE and .BO for BSE. Data refreshes on demand/cache expiry; this app does not run a background market feed.')

if not tickers:
    st.warning('Enter at least one valid ticker in the sidebar.'); st.stop()

# Load data once per app run/cache window
with st.spinner('Retrieving market and company data…'):
    histories={s:get_history(s,period) for s in list(dict.fromkeys(tickers+[benchmark]))}
    sector_hist={name:get_history(sym,period) for name,sym in SECTOR_INDICES.items()}

# top market tape
st.markdown('<div class="section-kicker">01 / Market overview</div>',unsafe_allow_html=True)
idx=histories.get(benchmark,pd.DataFrame())
if not idx.empty:
    last=idx.iloc[-1]; prev=idx.iloc[-2] if len(idx)>1 else last
    chg=pct(last['Close'],prev['Close'])
    m1,m2,m3,m4=st.columns(4)
    m1.metric('Benchmark close',fmt_num(last['Close']),f'{chg:+.2f}%' if pd.notna(chg) else None)
    m2.metric('Benchmark volume',fmt_num(last.get('Volume',np.nan)))
    m3.metric('Universe size',len(tickers))
    m4.metric('As-of date',idx.index[-1].strftime('%d %b %Y'))
else:
    st.warning('Benchmark history unavailable from the current data provider.')

# sector rotation
st.markdown('### Sector relative performance')
sector_rows=[]
for name,df in sector_hist.items():
    if len(df)>1:
        base=df['Close'].iloc[0]; end=df['Close'].iloc[-1]
        sector_rows.append({'Sector index':name,'Period return %':pct(end,base),'Last close':end,'As of':df.index[-1].strftime('%d %b %Y')})
if sector_rows:
    sdf=pd.DataFrame(sector_rows).sort_values('Period return %',ascending=False)
    c1,c2=st.columns([1.4,1])
    with c1: st.plotly_chart(px.bar(sdf,x='Period return %',y='Sector index',orientation='h',color='Period return %',color_continuous_scale='RdYlGn',title=f'Sector index returns · selected {period} window'),use_container_width=True)
    with c2: st.dataframe(sdf.style.format({'Period return %':'{:.2f}%','Last close':'{:,.2f}'}),use_container_width=True,hide_index=True)
else: st.caption('Sector index data unavailable. No sector ranking is fabricated.')

# watchlist price/breadth
st.markdown('<div class="section-kicker">02 / Equity monitor</div>',unsafe_allow_html=True)
rows=[]; return_series={}
for s in tickers:
    h=histories.get(s,pd.DataFrame())
    if h.empty: continue
    close=h['Close'].dropna(); r=pct(close.iloc[-1],close.iloc[0]) if len(close)>1 else np.nan
    daily=close.pct_change().dropna(); return_series[s]=daily
    rows.append({'Symbol':s,'Last close':close.iloc[-1],'Window return %':r,'20D return %':pct(close.iloc[-1],close.iloc[-21]) if len(close)>21 else np.nan,'20D volatility %':daily.tail(20).std()*np.sqrt(252)*100 if len(daily)>=20 else np.nan,'As of':close.index[-1].strftime('%d %b %Y')})
watch=pd.DataFrame(rows)
if not watch.empty:
    a,b,c=st.columns(3)
    a.metric('Stocks with price data',len(watch))
    a2=watch['Window return %'].gt(0).sum(); b.metric('Positive in selected window',f'{a2}/{len(watch)}')
    c.metric('Median window return',f"{watch['Window return %'].median():.2f}%")
    st.dataframe(watch.style.format({'Last close':'{:,.2f}','Window return %':'{:+.2f}%','20D return %':'{:+.2f}%','20D volatility %':'{:.2f}%'}),use_container_width=True,hide_index=True)
else: st.warning('No watchlist prices retrieved. Check symbols/provider availability.')

# Institutional flows: upload only, no fabricated feed
st.markdown('<div class="section-kicker">03 / Institutional flow intelligence</div>',unsafe_allow_html=True)
st.write('Upload an official NSE FII/DII activity CSV to analyse flows. This module intentionally does not invent daily institutional flows or scrape unofficial endpoints.')
flow_file=st.file_uploader('Upload FII/DII cash-market CSV',type=['csv'],key='flows')
if flow_file:
    try:
        flow=pd.read_csv(flow_file)
        st.write('Detected columns:',', '.join(map(str,flow.columns)))
        st.dataframe(flow.tail(30),use_container_width=True,hide_index=True)
        st.download_button('Download uploaded flow data',flow.to_csv(index=False).encode(),file_name='institutional_flows_review.csv',mime='text/csv')
        st.caption('Column mapping and net-flow calculations require the uploaded file schema to be confirmed. Raw source values are shown without relabelling.')
    except Exception as e: st.error(f'Could not read CSV: {e}')
else:
    st.info('No official flow file uploaded. FII/DII flow metrics are therefore marked unavailable. Obtain source data from NSE: https://www.nseindia.com/reports/fii-dii')

# fundamentals deep dive
st.markdown('<div class="section-kicker">04 / Earnings quality & valuation</div>',unsafe_allow_html=True)
selected=st.selectbox('Select company for fundamental review',tickers)
info,q,annual,cash,bs=get_fundamentals(selected)
price_hist=histories.get(selected,pd.DataFrame())
price=nval(price_hist['Close'].iloc[-1]) if not price_hist.empty else np.nan
pe=nval(info.get('trailingPE')); fpe=nval(info.get('forwardPE')); pb=nval(info.get('priceToBook')); ev_ebitda=nval(info.get('enterpriseToEbitda'))
marketcap=nval(info.get('marketCap'))
rev=statement_series(q,['Total Revenue','Operating Revenue','Revenue'])
net=statement_series(q,['Net Income','Net Income Common Stockholders'])
op=statement_series(q,['Operating Income'])
eps=statement_series(q,['Diluted EPS','Basic EPS'])
annual_rev=statement_series(annual,['Total Revenue','Operating Revenue','Revenue'])
annual_net=statement_series(annual,['Net Income','Net Income Common Stockholders'])
fcf=statement_series(cash,['Free Cash Flow'])
if fcf.empty:
    ocf=statement_series(cash,['Operating Cash Flow','Cash Flow From Continuing Operating Activities'])
    capex=statement_series(cash,['Capital Expenditure','Capital Expenditures'])
    if not ocf.empty and not capex.empty: fcf=ocf+capex

v1,v2,v3,v4,v5=st.columns(5)
v1.metric('Last price',fmt_num(price, f' {info.get("currency","INR")}'))
v2.metric('Trailing P/E',fmt_num(pe,'x'))
v3.metric('Forward P/E',fmt_num(fpe,'x'))
v4.metric('P/B',fmt_num(pb,'x'))
v5.metric('EV / EBITDA',fmt_num(ev_ebitda,'x'))
st.caption(f"{info.get('longName') or info.get('shortName') or selected} · {info.get('sector','Sector unavailable')} · Market cap {fmt_inr(marketcap)}. Valuation multiples are provider-reported snapshots, not historical percentile rankings.")

def chart_statement(s,title):
    if len(s):
        d=pd.DataFrame({'Period':s.index.astype(str),'Value':s.values}).sort_values('Period')
        st.plotly_chart(px.bar(d,x='Period',y='Value',title=title),use_container_width=True)
    else: st.caption(f'{title}: unavailable from provider.')
fc1,fc2=st.columns(2)
with fc1: chart_statement(rev,'Quarterly revenue'); chart_statement(eps,'Quarterly EPS')
with fc2: chart_statement(net,'Quarterly net income'); chart_statement(op,'Quarterly operating income')

# earnings quality table
quality=[]
for label,s in [('Quarterly revenue',rev),('Quarterly net income',net),('Quarterly EPS',eps),('Annual revenue',annual_rev),('Annual net income',annual_net),('Free cash flow',fcf)]:
    if len(s)>=2:
        latest=s.iloc[-1]; prior=s.iloc[-2]
        quality.append({'Metric':label,'Latest reported period':str(s.index[-1])[:10],'Latest value':latest,'Previous value':prior,'Sequential change %':pct(latest,prior)})
    else: quality.append({'Metric':label,'Latest reported period':'—','Latest value':np.nan,'Previous value':np.nan,'Sequential change %':np.nan})
st.markdown('#### Reported financial trend (provider data)')
st.dataframe(pd.DataFrame(quality).style.format({'Latest value':'{:,.2f}','Previous value':'{:,.2f}','Sequential change %':'{:+.2f}%'}),use_container_width=True,hide_index=True)

# Portfolio risk tool
st.markdown('<div class="section-kicker">05 / Portfolio risk laboratory</div>',unsafe_allow_html=True)
st.write('Enter portfolio weights for a simple historical risk diagnostic. This is not a live holdings connection or a regulated risk model.')
weights_text=st.text_area('Portfolio weights · one SYMBOL,WEIGHT per line', '\n'.join(f'{s},{100/len(tickers):.2f}' for s in tickers),height=110)
weights={}
for line in weights_text.splitlines():
    try:
        sym,w=line.split(','); weights[sym.strip().upper()]=float(w.strip())/100
    except Exception: pass
if weights:
    valid={s:w for s,w in weights.items() if s in return_series}
    total=sum(valid.values())
    if valid and total>0:
        rets=pd.concat({s:return_series[s] for s in valid},axis=1).dropna()
        wts=np.array([valid[s]/total for s in rets.columns])
        port=(rets*wts).sum(axis=1)
        stats=risk_stats(port); benchret=histories.get(benchmark,pd.DataFrame())
        p1,p2,p3,p4=st.columns(4)
        p1.metric('Annualised volatility',fmt_num(stats['vol'],'%'))
        p2.metric('Annualised Sharpe*',fmt_num(stats['sharpe']))
        p3.metric('Maximum drawdown',fmt_num(stats['maxdd'],'%'))
        p4.metric('Weights covered',f'{len(valid)}/{len(weights)}')
        st.plotly_chart(px.line((1+port).cumprod(),title='Portfolio growth of ₹1 · historical window').update_layout(yaxis_title='Growth multiple',xaxis_title='Date'),use_container_width=True)
        st.plotly_chart(px.imshow(rets.corr(),text_auto='.2f',aspect='auto',color_continuous_scale='RdBu',zmin=-1,zmax=1,title='Holdings return correlation'),use_container_width=True)
        st.caption('*Sharpe uses zero risk-free rate as a simplifying assumption. Portfolio weights are normalised over available symbols; this is not a full institutional VaR/attribution engine.')
    else: st.warning('No portfolio symbols match the downloaded price history.')

# derivatives data input, no invented positioning
st.markdown('<div class="section-kicker">06 / Derivatives & positioning workspace</div>',unsafe_allow_html=True)
st.write('Use this workspace to inspect an exported option-chain CSV. No live option-chain or participant-positioning feed is claimed.')
opt_file=st.file_uploader('Upload option-chain CSV (optional)',type=['csv'],key='options')
if opt_file:
    try:
        od=pd.read_csv(opt_file); st.dataframe(od.head(100),use_container_width=True,hide_index=True)
        st.caption('Raw uploaded chain displayed. PCR, IV skew and OI concentration will only be calculated after the file columns and call/put schema are verified.')
    except Exception as e: st.error(f'Could not read option-chain CSV: {e}')
else: st.caption('No option-chain file uploaded. PCR, IV, max pain and participant positioning are not available in this version.')

# Data audit and exports
st.markdown('<div class="section-kicker">07 / Data audit & exports</div>',unsafe_allow_html=True)
audit=pd.DataFrame([
 {'Module':'Prices / historical returns','Source':'Yahoo Finance via yfinance','Status':'Retrieved' if not watch.empty else 'Unavailable','Limitation':'May be delayed, incomplete or adjusted.'},
 {'Module':'Company financial statements','Source':'Yahoo Finance via yfinance','Status':'Retrieved' if not q.empty or not annual.empty else 'Unavailable','Limitation':'Provider transcription; verify against filings.'},
 {'Module':'FII / DII flows','Source':'User-uploaded official NSE CSV','Status':'Uploaded' if flow_file else 'Not supplied','Limitation':'No automatic official feed in this build.'},
 {'Module':'Options / participant positioning','Source':'User-uploaded option-chain CSV','Status':'Uploaded' if opt_file else 'Not supplied','Limitation':'No live chain or participant data feed.'},
 {'Module':'Historical valuation percentiles / analyst revisions','Source':'Not included','Status':'Not available','Limitation':'Requires validated point-in-time datasets.'}
])
st.dataframe(audit,use_container_width=True,hide_index=True)
if not watch.empty:
    st.download_button('Export equity monitor CSV',watch.to_csv(index=False).encode(),file_name='market_peak_equity_monitor.csv',mime='text/csv')
st.caption(f'Workspace refreshed: {datetime.now().strftime("%d %b %Y, %H:%M:%S")} local app time. Free-data edition · No paid API keys · No trade execution.')
st.caption('Research discipline: a risk flag is a prompt for investigation, not a sell recommendation. Never treat a single valuation multiple, flow observation or model output as proof of an earnings peak.')
