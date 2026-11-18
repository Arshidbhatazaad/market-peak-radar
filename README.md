# Market Peak Radar — free local dashboard

## What it does
- Runs in a browser on your own computer.
- Retrieves available company profile, valuation and financial-statement data using the open-source `yfinance` Python package.
- Supports NSE (`.NS`) and BSE (`.BO`) symbols where Yahoo Finance has coverage.
- Calculates a transparent preliminary warning score from available quarterly/annual revenue, net income, operating margin, EPS and current P/E context.
- Shows missing data explicitly; it does not invent analyst revisions, historical P/E percentiles, order-book data or management guidance.
- Saves your watchlist locally and exports scan results to CSV.
- Includes weekly, monthly, quarterly and annual research checklists.

## Important data limitations
Yahoo Finance is a third-party source. Its data may be delayed, incomplete, inconsistent or unavailable. `yfinance` is an unofficial open-source interface, not an official NSE/BSE API. Do not use the output as a sole basis for investment decisions.
This app does NOT scrape Screener or Trendlyne, does not bypass logins, and does not claim to have a paid/official exchange feed.
Analyst estimate revisions, historical valuation percentiles, peer comparisons and transcript analysis are deliberately marked as outside the MVP because there is no reliable, free, permitted universal feed for those data.
The dashboard refreshes when you press Refresh or reload the app. It does not run while your computer is off or the app is closed.

## Install (Windows)
1. Install Python 3.10 or newer from python.org. During installation, enable "Add Python to PATH".
2. Extract this ZIP file.
3. Open the extracted folder.
4. Double-click `run_windows.bat`.
5. Wait for the terminal to install dependencies and start Streamlit.
6. Your browser should open at `http://localhost:8501`. If it does not, copy that address into Chrome.

## Install (macOS / Linux)
Open a terminal in this folder and run:
```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```
Then open `http://localhost:8501`.

## Symbols
Examples:
- `RELIANCE.NS`
- `TCS.NS`
- `HDFCBANK.NS`
- `INFY.NS`
- `ITC.NS`
Use the sidebar to edit and save your watchlist.

## Score interpretation
The score is a heuristic, not a statistically validated forecast. A high score means multiple available fundamentals are weakening; a low score does not prove the stock is safe. Missing fields reduce data coverage and should prompt manual verification, not a favourable inference.

## Troubleshooting
- If no data appears, check internet connectivity and the ticker suffix.
- Yahoo Finance may throttle requests. Try a smaller watchlist and wait before refreshing.
- If package installation fails, install Python 3.10+ and run `python -m pip install -r requirements.txt` manually.
