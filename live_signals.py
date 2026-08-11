import time
import requests
import io
import yfinance as yf
import pandas as pd
import numpy as np
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings('ignore')

# ==================== CONFIGURATION ====================
TELEGRAM_BOT_TOKEN = "7672647020:AAHmA4DOWqbV5rqN3K2rtDax-uA5rmgD7YQ"
TELEGRAM_CHAT_ID = "1751317811"


CAPITAL = 100000          # Allocation per Position
RISK_PER_TRADE = 0.015   # 1.5% Risk per trade
MAX_THREADS = 15          # Multi-threading workers for speed
# =======================================================

def get_nse_universe() -> list:
    """Fetches the latest official master stock list directly from NSE Archives."""
    print("🌐 Fetching complete NSE Equity Universe from NSE India...")
    url = "https://archives.nseindia.com/content/equity/EQUITY_L.csv"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            df = pd.read_csv(io.StringIO(res.text))
            # Exclude SME / ETF Series if necessary, focus on EQ Series
            df_eq = df[df['SERIES'] == 'EQ'] if 'SERIES' in df.columns else df
            symbols = [f"{sym.strip()}.NS" for sym in df_eq['SYMBOL'].dropna().unique()]
            print(f"✅ Successfully loaded {len(symbols)} NSE Equity Stocks!")
            return symbols
    except Exception as e:
        print(f"⚠️ NSE Fetch failed ({e}), using fallback Liquid Universe...")
    
    # Fallback in case NSE site blocks connection
    return ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "WIPRO.NS", "DLF.NS"]

def send_telegram_alert(message: str):
    """Sends realtime signal formatted alert to Telegram."""
    if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"❌ Telegram Alert Error: {e}")

def fetch_and_analyze(symbol: str, nifty_df: pd.DataFrame):
    """Analyzes Real-time Stock Setup for VMS PRO v4 Criteria."""
    try:
        df = yf.download(symbol, period="1y", interval="1d", auto_adjust=False, progress=False)
        if df.empty or len(df) < 60:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close_price = df['Adj Close'] if 'Adj Close' in df.columns else df['Close']
        
        # Avoid Penny Stocks (Price < 20) or Illiquid Stocks
        if close_price.iloc[-1] < 20 or df['Volume'].iloc[-1] < 50000:
            return None

        # Technical Indicators
        df['20_SMA'] = close_price.rolling(20).mean()
        df['50_SMA'] = close_price.rolling(50).mean()
        df['200_SMA'] = close_price.rolling(200).mean()
        df['Vol_20SMA'] = df['Volume'].rolling(20).mean()
        
        # ATR Calculation
        high_low = df['High'] - df['Low']
        high_close = (df['High'] - close_price.shift()).abs()
        low_close = (df['Low'] - close_price.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df['ATR'] = tr.rolling(14).mean()

        # Relative Strength vs Nifty Benchmark
        idx_close = nifty_df['Adj Close'] if 'Adj Close' in nifty_df.columns else nifty_df['Close']
        stock_ret = close_price.pct_change(21)
        index_ret = idx_close.pct_change(21)
        df['RS'] = stock_ret - index_ret
        df['RS_Rank'] = df['RS'].rolling(100).rank(pct=True) * 100

        # Monthly Pivot Calculation
        df['Prev_Month_High'] = df['High'].shift(20)
        df['Prev_Month_Low'] = df['Low'].shift(20)
        df['Prev_Month_Close'] = close_price.shift(20)
        df['Monthly_Pivot'] = (df['Prev_Month_High'] + df['Prev_Month_Low'] + df['Prev_Month_Close']) / 3

        latest = df.iloc[-1]

        # VMS PRO Setup Conditions Check
        c1 = latest['Close'] > latest['Monthly_Pivot']
        c2 = latest['Close'] > latest['20_SMA']
        c3 = latest['20_SMA'] > latest['50_SMA']
        c4 = latest['Close'] > latest['200_SMA']
        c5 = latest['Volume'] > 1.2 * latest['Vol_20SMA']
        c6 = latest['RS_Rank'] >= 65

        # VMS Confluence Score (Out of 100)
        score = sum([c1, c2, c3, c4, c5, c6]) * 16.66

        if score >= 80:
            current_price = round(latest['Close'], 2)
            trigger_price = round(latest['High'] + 0.50, 2)
            atr = latest['ATR']
            sl_dist = round(2.0 * atr, 2)
            stop_loss = round(trigger_price - sl_dist, 2)
            target_1 = round(trigger_price + (1.5 * sl_dist), 2)
            target_2 = round(trigger_price + (2.5 * sl_dist), 2)
            
            qty = int((CAPITAL * RISK_PER_TRADE) / sl_dist) if sl_dist > 0 else 0

            return {
                "symbol": symbol.replace(".NS", ""),
                "score": round(score, 1),
                "current_price": current_price,
                "trigger_price": trigger_price,
                "stop_loss": stop_loss,
                "target_1": target_1,
                "target_2": target_2,
                "qty": qty,
                "rs_rank": round(latest['RS_Rank'], 1)
            }
    except Exception:
        pass
    return None

def run_live_universe_scanner():
    print(f"\n🚀 Starting Full NSE Scanner... [{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
    
    # 1. Fetch Benchmark Index Data
    nifty = yf.download("^NSEI", period="1y", interval="1d", auto_adjust=False, progress=False)
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)

    # 2. Get 1000+ NSE Stock List
    symbols = get_nse_universe()
    
    signals_found = []
    
    # 3. Parallel Scanning via ThreadPool
    print(f"⚡ Parallel Scanning {len(symbols)} stocks with {MAX_THREADS} threads...")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(fetch_and_analyze, sym, nifty): sym for sym in symbols}
        for future in as_completed(futures):
            res = future.result()
            if res:
                signals_found.append(res)
                
                # Send Instant Telegram Alert for High Confluence Signals
                alert_msg = (
                    f"⚡ *VMS PRO v4.0 BREAKOUT ALERT* ⚡\n\n"
                    f"📌 *Stock:* `{res['symbol']}`\n"
                    f"🎯 *Quant Score:* `{res['score']}/100`\n"
                    f"💪 *Relative Strength:* `{res['rs_rank']}% percentile`\n\n"
                    f"📈 *BUY TRIGGER ABOVE:* ₹{res['trigger_price']}\n"
                    f"🛑 *STOP LOSS:* ₹{res['stop_loss']}\n"
                    f"🎯 *TARGET 1 (1:1.5):* ₹{res['target_1']}\n"
                    f"🚀 *TARGET 2 (1:2.5):* ₹{res['target_2']}\n\n"
                    f"🔢 *Recommended Position Size:* `{res['qty']} Shares`\n"
                    f"⏰ *Scan Time:* {datetime.datetime.now().strftime('%I:%M %p')}\n"
                )
                send_telegram_alert(alert_msg)
                print(f"🔥 BREAKOUT DETECTED: {res['symbol']} | Score: {res['score']}")

    elapsed = round(time.time() - start_time, 2)
    print(f"✅ Scan Complete in {elapsed}s! Found {len(signals_found)} Qualified Trades.")

if __name__ == "__main__":
    send_telegram_alert("🚀 *VMS PRO v4.0 Full NSE Master Scanner Active!*")
    run_live_universe_scanner()