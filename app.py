import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timezone
from pathlib import Path
import json, time

APP_DIR = Path(__file__).parent
WATCHLIST_FILE = APP_DIR / "watchlist.csv"
CACHE_FILE = APP_DIR / "last_scan.json"

st.set_page_config(page_title="Market Peak Radar", page_icon="📡", layout="wide")
st.title("📡 Market Peak Radar")
st.caption("Free Indian-equity earnings and valuation research dashboard | Data via Yahoo Finance / yfinance")

st.warning(
    "Data limitations: Yahoo Finance data is third-party, may be delayed, incomplete, inconsistent or unavailable. "
    "This is a research aid, not investment advice or an official NSE/BSE feed. Verify every material figure against "
    "company filings. No paid APIs, credentials, or hidden scraping are used."
)

DEFAULT = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS"]

def load_watchlist():
    if WATCHLIST_FILE.exists():
        try:
            vals = pd.read_csv(WATCHLIST_FILE)["Ticker"].dropna().astype(str).str.upper().tolist()
            if vals:
                return list(dict.fromkeys(vals))
        except Exception:
            pass
    return DEFAULT.copy()

def save_watchlist(vals):
    pd.DataFrame({"Ticker": vals}).to_csv(WATCHLIST_FILE, index=False)

def norm_statement(df):
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    try:
        out.columns = pd.to_datetime(out.columns)
        out = out.reindex(sorted(out.columns, reverse=True), axis=1)
    except Exception:
        pass
    return out

def find_row(df, candidates):
    if df is None or df.empty:
        return None
    names = {str(x).lower().replace("_", " "): x for x in df.index}
    for cand in candidates:
        c = cand.lower()
        for low, original in names.items():
            if c == low or c in low:
                return original
    return None

def series_for(df, candidates):
    row = find_row(df, candidates)
    if row is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(df.loc[row], errors="coerce").dropna()
    try:
        s.index = pd.to_datetime(s.index)
        s = s.sort_index(ascending=False)
    except Exception:
        pass
    return s

def safe_num(x):
    try:
        if x is None or pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None

def pct_change(a, b):
    if b is None or b == 0 or a is None:
        return None
    return (a / b - 1) * 100

def fetch_company(ticker):
    t = yf.Ticker(ticker)
    info = {}
    try:
        info = t.get_info()
    except Exception:
        try:
            info = t.info
        except Exception:
            info = {}
    q = norm_statement(t.quarterly_income_stmt)
    annual = norm_statement(t.income_stmt)
    cash = norm_statement(t.quarterly_cashflow)
    return t, info, q, annual, cash

def analyse(ticker):
    t, info, q, annual, cash = fetch_company(ticker)
    rev = series_for(q, ["Total Revenue", "Operating Revenue", "Revenue"])
    net = series_for(q, ["Net Income", "Net Income Common Stockholders"])
    opinc = series_for(q, ["Operating Income"])
    eps = series_for(q, ["Diluted EPS", "Basic EPS"])
    annual_rev = series_for(annual, ["Total Revenue", "Operating Revenue", "Revenue"])
    annual_net = series_for(annual, ["Net Income", "Net Income Common Stockholders"])

    metrics = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector", "Unavailable"),
        "industry": info.get("industry", "Unavailable"),
        "price": safe_num(info.get("currentPrice") or info.get("regularMarketPrice")),
        "trailing_pe": safe_num(info.get("trailingPE")),
        "forward_pe": safe_num(info.get("forwardPE")),
        "market_cap": safe_num(info.get("marketCap")),
        "dividend_yield": safe_num(info.get("dividendYield")),
        "currency": info.get("currency", "INR"),
        "rev": rev, "net": net, "opinc": opinc, "eps": eps,
        "annual_rev": annual_rev, "annual_net": annual_net,
        "cash": cash,
    }
    return metrics

def score_metrics(m):
    score, details = 0, []
    rev, net, op, eps = m["rev"], m["net"], m["opinc"], m["eps"]

    # Latest quarter vs same quarter one year earlier, and deceleration vs preceding YoY comparison.
    if len(rev) >= 5:
        latest = safe_num(rev.iloc[0]); year_ago = safe_num(rev.iloc[4])
        prior_q = safe_num(rev.iloc[1]); prior_year_ago = safe_num(rev.iloc[5]) if len(rev) >= 6 else None
        g1 = pct_change(latest, year_ago)
        g0 = pct_change(prior_q, prior_year_ago) if prior_year_ago is not None else None
        if g1 is not None:
            if g1 < 0:
                score += 20; details.append(("Revenue contracting YoY", 20, f"{g1:.1f}%"))
            elif g0 is not None and g1 < g0 - 10:
                score += 12; details.append(("Revenue growth decelerating", 12, f"{g0:.1f}% → {g1:.1f}%"))
            elif g0 is not None and g1 < g0 - 3:
                score += 6; details.append(("Revenue growth slowing", 6, f"{g0:.1f}% → {g1:.1f}%"))
    else:
        details.append(("Revenue trend", None, "Insufficient quarterly history"))

    if len(net) >= 5:
        ng = pct_change(safe_num(net.iloc[0]), safe_num(net.iloc[4]))
        if ng is not None and ng < 0:
            score += 15; details.append(("Net income contracting YoY", 15, f"{ng:.1f}%"))
        elif ng is not None:
            details.append(("Net income YoY", 0, f"{ng:.1f}%"))
    else:
        details.append(("Net income trend", None, "Insufficient quarterly history"))

    if len(op) >= 2 and len(rev) >= 2:
        m0 = (safe_num(op.iloc[0]) / safe_num(rev.iloc[0])) if safe_num(rev.iloc[0]) not in (None, 0) else None
        m1 = (safe_num(op.iloc[1]) / safe_num(rev.iloc[1])) if safe_num(rev.iloc[1]) not in (None, 0) else None
        if m0 is not None and m1 is not None:
            delta = (m0 - m1) * 100
            if delta < -2:
                score += 12; details.append(("Operating margin contracted QoQ", 12, f"{delta:.2f} percentage points"))
            elif delta < -0.5:
                score += 5; details.append(("Operating margin softened QoQ", 5, f"{delta:.2f} percentage points"))
            else:
                details.append(("Operating margin QoQ", 0, f"{delta:+.2f} percentage points"))

    if len(eps) >= 5:
        eg = pct_change(safe_num(eps.iloc[0]), safe_num(eps.iloc[4]))
        if eg is not None and eg < 0:
            score += 15; details.append(("Quarterly EPS contracting YoY", 15, f"{eg:.1f}%"))
        elif eg is not None:
            details.append(("Quarterly EPS YoY", 0, f"{eg:.1f}%"))
    else:
        details.append(("EPS trend", None, "Insufficient quarterly EPS history"))

    # Annual cross-check
    if len(m["annual_rev"]) >= 2:
        ag = pct_change(safe_num(m["annual_rev"].iloc[0]), safe_num(m["annual_rev"].iloc[1]))
        if ag is not None and ag < 0:
            score += 8; details.append(("Annual revenue contracting", 8, f"{ag:.1f}%"))
        else:
            details.append(("Annual revenue growth", 0, "Not negative" if ag is not None else "Unavailable"))
    else:
        details.append(("Annual revenue", None, "Insufficient annual history"))

    # Valuation: current multiple is a context flag, not a peak detector.
    pe = m["trailing_pe"]
    if pe is not None and pe > 0:
        if pe >= 60:
            score += 8; details.append(("High trailing P/E context", 8, f"{pe:.1f}x; not a sell signal alone"))
        elif pe >= 40:
            score += 4; details.append(("Elevated trailing P/E context", 4, f"{pe:.1f}x; compare with peers"))
        else:
            details.append(("Trailing P/E context", 0, f"{pe:.1f}x"))
    else:
        details.append(("Trailing P/E", None, "Unavailable / not meaningful"))

    # Cap and report coverage
    score = min(100, score)
    available = sum(1 for _, pts, _ in details if pts is not None)
    coverage = round(available / max(1, len(details)) * 100)
    if coverage < 40:
        label = "Insufficient data"
    elif score >= 45:
        label = "Elevated warning"
    elif score >= 25:
        label = "Watch"
    else:
        label = "No major warning detected"
    return score, label, coverage, details

def money(x):
    if x is None: return "—"
    if abs(x) >= 1e12: return f"₹{x/1e12:.2f}T"
    if abs(x) >= 1e9: return f"₹{x/1e9:.2f}B"
    if abs(x) >= 1e7: return f"₹{x/1e7:.2f}Cr"
    return f"₹{x:,.2f}"

with st.sidebar:
    st.header("Universe & controls")
    current = load_watchlist()
    raw = st.text_area("Watchlist (Yahoo Finance symbols, one per line)", "\n".join(current), height=220)
    tickers = list(dict.fromkeys([x.strip().upper() for x in raw.replace(",", "\n").splitlines() if x.strip()]))
    if st.button("Save watchlist", use_container_width=True):
        save_watchlist(tickers)
        st.success("Watchlist saved locally.")
    st.caption("Indian symbols usually end in .NS (NSE) or .BO (BSE). Example: RELIANCE.NS")
    st.divider()
    st.caption("No API key required. Refreshes occur when you open the app or press refresh; this local app does not run while your device is off.")

if not tickers:
    st.info("Add at least one ticker in the sidebar.")
    st.stop()

col1, col2 = st.columns([1, 3])
with col1:
    refresh = st.button("🔄 Refresh data now", type="primary", use_container_width=True)
with col2:
    st.caption(f"Last page load: {datetime.now().strftime('%d %b %Y, %H:%M:%S')} local time. Data timestamps are provider-dependent.")

if "results" not in st.session_state or refresh:
    results, errors = [], []
    progress = st.progress(0)
    status = st.empty()
    for i, ticker in enumerate(tickers):
        status.write(f"Fetching {ticker} ({i+1}/{len(tickers)})…")
        try:
            m = analyse(ticker)
            score, label, coverage, details = score_metrics(m)
            m.update({"score": score, "label": label, "coverage": coverage, "details": details})
            results.append(m)
        except Exception as e:
            errors.append((ticker, str(e)[:240]))
        progress.progress((i+1)/len(tickers))
        time.sleep(0.15)
    st.session_state["results"] = results
    st.session_state["errors"] = errors
    st.session_state["scan_time"] = datetime.now().isoformat(timespec="seconds")
    status.empty()
    progress.empty()

results = st.session_state.get("results", [])
errors = st.session_state.get("errors", [])
if not results:
    st.error("No company data was retrieved. Check ticker symbols and internet connectivity.")
    for e in errors: st.write(e)
    st.stop()

df = pd.DataFrame([{
    "Ticker": m["ticker"], "Company": m["name"], "Price": m["price"],
    "Trailing P/E": m["trailing_pe"], "Forward P/E": m["forward_pe"],
    "Risk score": m["score"], "Signal": m["label"], "Data coverage": f'{m["coverage"]}%'
} for m in results])

st.subheader("Watchlist overview")
a,b,c,d = st.columns(4)
a.metric("Stocks retrieved", len(results))
b.metric("Elevated warnings", sum(m["label"] == "Elevated warning" for m in results))
c.metric("Watch signals", sum(m["label"] == "Watch" for m in results))
d.metric("Scan time", st.session_state.get("scan_time", "—").split("T")[-1] if st.session_state.get("scan_time") else "—")
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Company deep dive")
selected = st.selectbox("Select a company", [m["ticker"] for m in results])
m = next(x for x in results if x["ticker"] == selected)
score, label, coverage, details = m["score"], m["label"], m["coverage"], m["details"]

x1,x2,x3,x4 = st.columns(4)
x1.metric("Peak-risk warning score", f"{score}/100")
x2.metric("Assessment", label)
x3.metric("Data coverage", f"{coverage}%")
x4.metric("Current price", f'{m["currency"]} {m["price"]:,.2f}' if m["price"] is not None else "Unavailable")

st.write(f"**{m['name']}** · {m['sector']} · {m['industry']}")
v1,v2,v3 = st.columns(3)
v1.metric("Trailing P/E", f'{m["trailing_pe"]:.2f}x' if m["trailing_pe"] else "Unavailable")
v2.metric("Forward P/E", f'{m["forward_pe"]:.2f}x' if m["forward_pe"] else "Unavailable")
v3.metric("Market capitalisation", money(m["market_cap"]))

st.caption("The score is a transparent, preliminary heuristic based only on available reported data. Analyst estimate revisions, historical P/E percentile, peer valuation, order-book changes and management guidance are not included unless separately sourced and verified.")
st.markdown("#### Signal breakdown")
breakdown = pd.DataFrame(details, columns=["Indicator", "Points", "Observation"])
st.dataframe(breakdown, use_container_width=True, hide_index=True)

def plot_series(s, title, ytitle):
    if s is not None and len(s):
        chart = pd.DataFrame({"Period": pd.to_datetime(s.index).astype(str), ytitle: s.values}).sort_values("Period")
        st.plotly_chart(px.bar(chart, x="Period", y=ytitle, title=title), use_container_width=True)
    else:
        st.info(f"{title}: provider data unavailable.")

left,right = st.columns(2)
with left:
    plot_series(m["rev"], "Quarterly revenue", "Revenue")
    plot_series(m["eps"], "Quarterly EPS", "EPS")
with right:
    plot_series(m["net"], "Quarterly net income", "Net income")
    plot_series(m["annual_rev"], "Annual revenue", "Revenue")

st.markdown("#### Research cadence checklist")
cadence = {
    "Weekly": ["Refresh price and relative strength against Nifty 50", "Review major company announcements", "Check whether any thesis-breaking news appeared"],
    "Monthly": ["Compare valuation with available peer data", "Review EPS estimate revisions where independently available", "Record P/E and price snapshot for future comparison"],
    "Quarterly": ["Review revenue, operating profit, margins and EPS", "Compare year-on-year and sequential growth", "Read results presentation and earnings-call transcript", "Check operating cash flow against reported profit"],
    "Annually": ["Read annual report and auditor observations", "Assess normalized earnings and cyclicality", "Review capital allocation, debt and return on capital", "Reassess long-term investment thesis"]
}
for period, tasks in cadence.items():
    with st.expander(period + " research routine", expanded=(period=="Weekly")):
        for task in tasks:
            st.checkbox(task, key=f"{selected}_{period}_{task}")

st.markdown("#### Export")
export = df.to_csv(index=False).encode("utf-8")
st.download_button("Download watchlist scan as CSV", export, file_name="market_peak_radar_scan.csv", mime="text/csv")

if errors:
    with st.expander(f"Data retrieval issues ({len(errors)})"):
        for ticker, err in errors:
            st.write(f"**{ticker}:** {err}")

st.divider()
st.caption("Built for research and education. No trade execution. No guaranteed peak prediction. Verify financial statements with official exchange/company disclosures before acting.")
