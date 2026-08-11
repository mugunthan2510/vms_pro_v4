import io
import time
import asyncio
import datetime
import requests
import warnings
import pandas as pd
import numpy as np
import yfinance as yf
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

warnings.filterwarnings('ignore')

# Config
MAX_THREADS = 8
RANKINGS_CACHE: List[Dict[str, Any]] = []
LAST_UPDATED_TIME: str = "--:--:--"

CORE_LIQUID_UNIVERSE = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "LTIM.NS", "LT.NS", "HINDUNILVR.NS",
    "AXISBANK.NS", "KOTAKBANK.NS", "M&M.NS", "TATAMOTORS.NS", "SUNPHARMA.NS",
    "NTPC.NS", "TITAN.NS", "MARUTI.NS", "BAJFINANCE.NS", "TATASTEEL.NS",
    "POWERGRID.NS", "ADANIENT.NS", "ASIANPAINT.NS", "COALINDIA.NS", "JSWSTEEL.NS",
    "ADANIPORTS.NS", "HCLTECH.NS", "ULTRACEMCO.NS", "ONGC.NS", "GRASIM.NS",
    "TECHM.NS", "CIPLA.NS", "HEROMOTOCO.NS", "WIPRO.NS", "DLF.NS"
]

app = FastAPI(title="VMS PRO v4.0 Quant Terminal")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")
except Exception as e:
    print(f"Mount note: {e}")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass

manager = ConnectionManager()

def evaluate_stock_vms(symbol: str, nifty_close: pd.Series) -> Dict[str, Any]:
    try:
        # Download individual ticker data freshly
        ticker_df = yf.Ticker(symbol).history(period="1y", interval="1d")
        
        if ticker_df is None or ticker_df.empty or len(ticker_df) < 50:
            return None

        clean_df = ticker_df.copy()
        
        close_price = clean_df['Close']
        latest_close = float(close_price.iloc[-1])
        
        if pd.isna(latest_close) or latest_close < 10:
            return None

        # Technical Calculations
        clean_df['20_SMA'] = close_price.rolling(20).mean()
        clean_df['50_SMA'] = close_price.rolling(50).mean()
        clean_df['200_SMA'] = close_price.rolling(200).mean()
        clean_df['Vol_20SMA'] = clean_df['Volume'].rolling(20).mean()

        high_low = clean_df['High'] - clean_df['Low']
        high_close = (clean_df['High'] - close_price.shift()).abs()
        low_close = (clean_df['Low'] - close_price.shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        clean_df['ATR'] = tr.rolling(14).mean()

        # Relative Strength Calculation vs Nifty 50
        if nifty_close is not None and not nifty_close.empty:
            stock_ret = close_price.pct_change(21)
            index_ret = nifty_close.pct_change(21)
            clean_df['RS'] = stock_ret - index_ret
            clean_df['RS_Rank'] = clean_df['RS'].rolling(100).rank(pct=True) * 100
        else:
            clean_df['RS_Rank'] = 50

        # Monthly & Weekly Pivot Calculations (Last Month High/Low/Close)
        monthly_df = clean_df['Close'].resample('ME').ohlc() if hasattr(pd, 'date_range') else clean_df['Close'].resample('M').ohlc()
        if len(monthly_df) >= 2:
            prev_month = monthly_df.iloc[-2]
            monthly_pivot = (prev_month['high'] + prev_month['low'] + prev_month['close']) / 3.0
        else:
            monthly_pivot = latest_close

        weekly_df = clean_df['Close'].resample('W').ohlc()
        if len(weekly_df) >= 2:
            prev_week = weekly_df.iloc[-2]
            weekly_pivot = (prev_week['high'] + prev_week['low'] + prev_week['close']) / 3.0
        else:
            weekly_pivot = monthly_pivot * 0.99

        latest = clean_df.iloc[-1]

        c1 = float(latest['Close']) > monthly_pivot
        c2 = float(latest['Close']) > float(latest['20_SMA'])
        c3 = float(latest['20_SMA']) > float(latest['50_SMA'])
        c4 = float(latest['Close']) > float(latest['200_SMA'])
        c5 = float(latest['Volume']) > (1.0 * float(latest['Vol_20SMA']))
        c6 = float(latest['RS_Rank']) >= 50

        score = int(round(sum([c1, c2, c3, c4, c5, c6]) * 16.66))

        clean_symbol = symbol.replace(".NS", "")
        current_price = round(latest_close, 2)
        m_pivot = round(monthly_pivot, 2)
        w_pivot = round(weekly_pivot, 2)
        rs_rank = int(round(float(latest['RS_Rank']))) if not pd.isna(latest['RS_Rank']) else 50

        if score >= 80:
            signal = "VALID TRADE"
        elif score >= 60:
            signal = "WATCHLIST"
        else:
            signal = "NO TRADE"

        return {
            "symbol": clean_symbol,
            "score": score,
            "total_score": score,
            "monthly_pivot": f"Monthly: ₹{m_pivot} | W-Pivot: ₹{w_pivot}",
            "m_pivot": m_pivot,
            "w_pivot": w_pivot,
            "signal": signal,
            "swing_signal": f"{signal} | RS PERCENTILE: {rs_rank}%",
            "rs_rank": rs_rank,
            "price": current_price,
            "atr": round(float(latest['ATR']), 2) if not pd.isna(latest['ATR']) else 10.0
        }
    except Exception as e:
        print(f"Error evaluating {symbol}: {e}")
        return None

def run_vms_pro_scan():
    global RANKINGS_CACHE, LAST_UPDATED_TIME
    print("⏳ Executing Quant Scan Engine...")
    
    try:
        nifty_data = yf.Ticker("^NSEI").history(period="1y", interval="1d")
        nifty_close = nifty_data['Close'] if not nifty_data.empty else None
    except Exception as e:
        print(f"Nifty fetch warning: {e}")
        nifty_close = None

    evaluated_list = []
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(evaluate_stock_vms, sym, nifty_close): sym for sym in CORE_LIQUID_UNIVERSE}
        for future in as_completed(futures):
            res = future.result()
            if res:
                evaluated_list.append(res)

    evaluated_list.sort(key=lambda x: x['score'], reverse=True)
    for idx, item in enumerate(evaluated_list, 1):
        item['rank'] = idx

    RANKINGS_CACHE = evaluated_list
    LAST_UPDATED_TIME = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"✅ Updated rankings cache with {len(RANKINGS_CACHE)} evaluated stocks at {LAST_UPDATED_TIME}.")

async def background_scanner_loop():
    while True:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, run_vms_pro_scan)
            await manager.broadcast({
                "type": "log", 
                "message": f"[SYS] Swing Rankings updated successfully. ({len(RANKINGS_CACHE)} stocks evaluated)"
            })
        except Exception as e:
            print(f"⚠️ Scanner Loop Exception: {e}")
        await asyncio.sleep(600)

@app.on_event("startup")
async def startup_event():
    print("🚀 Initializing VMS PRO V4 Core Trading System...")
    asyncio.create_task(background_scanner_loop())

@app.get("/api/rankings")
def get_rankings():
    if len(RANKINGS_CACHE) == 0:
        run_vms_pro_scan()
    return JSONResponse({
        "status": "success",
        "last_updated": LAST_UPDATED_TIME,
        "total_evaluated": len(RANKINGS_CACHE),
        "rankings": RANKINGS_CACHE,
        "data": RANKINGS_CACHE
    })

@app.get("/api/scan")
def trigger_manual_scan():
    run_vms_pro_scan()
    return JSONResponse({
        "status": "success",
        "message": f"Scan complete! {len(RANKINGS_CACHE)} stocks loaded.",
        "rankings": RANKINGS_CACHE
    })

@app.websocket("/ws/live-ticks")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        await websocket.send_json({"type": "status", "feed": "CONNECTED", "engines": "9 / 9"})
        while True:
            await asyncio.sleep(10)
            await websocket.send_json({"type": "ping", "time": datetime.datetime.now().strftime("%H:%M:%S")})
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)