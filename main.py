import os
import time
import logging
import threading
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import pyotp
from SmartApi import SmartConnect

# Local module imports
from config.settings import (
    SMARTAPI_KEY,
    SMARTAPI_CLIENT,
    SMARTAPI_PIN,
    SMARTAPI_TOTP,
    WATCHLIST,
    HOST,
    PORT
)
from broker.smart_stream import SmartStreamManager
from engines.rs.engine import RelativeStrengthEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("VMS_PRO_MAIN")

# Initialize FastAPI App
app = FastAPI(title="VMS PRO V4 Dashboard")

# Global Cache for RS Engine Results
LATEST_ANALYSIS_RESULTS = {}


# --- HEALTH CHECK ENDPOINTS FOR RENDER ---
@app.get("/healthz", status_code=200)
@app.get("/health", status_code=200)
def health_check():
    """Health check endpoint required for Render deployment."""
    return JSONResponse(
        content={
            "status": "ok",
            "service": "VMS PRO V4 Quant Engine",
            "watchlist_count": len(WATCHLIST),
            "cached_results": len(LATEST_ANALYSIS_RESULTS)
        }
    )


# --- DASHBOARD UI ENDPOINTS ---
@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Renders basic Dashboard UI to verify server response."""
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VMS PRO V4 - Live Dashboard</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 20px; }}
            h1 {{ color: #38bdf8; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 20px; background-color: #1e293b; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #334155; }}
            th {{ background-color: #0284c7; color: white; }}
            tr:hover {{ background-color: #334155; }}
            .badge {{ background-color: #16a34a; padding: 4px 8px; border-radius: 4px; font-weight: bold; }}
            .no-data {{ color: #f59e0b; padding: 15px; font-style: italic; text-align: center; }}
        </style>
    </head>
    <body>
        <h1>🚀 VMS PRO V4 - Live Market Dashboard</h1>
        <p>Status: <span class="badge">ACTIVE STREAMING</span> | Total Tracked Stocks: {len(WATCHLIST)}</p>
        
        <h2>Top Relative Strength Leaders</h2>
        <table>
            <tr>
                <th>Symbol</th>
                <th>RS Score</th>
                <th>RS Percentile</th>
            </tr>
    """
    
    if LATEST_ANALYSIS_RESULTS:
        sorted_stocks = sorted(
            LATEST_ANALYSIS_RESULTS.items(), 
            key=lambda item: item[1].get("rs_percentile", 0) if isinstance(item[1], dict) else 0, 
            reverse=True
        )
        
        for symbol, metrics in sorted_stocks[:20]:
            rs_score = metrics.get('rs_score', 0) if isinstance(metrics, dict) else 0
            rs_pct = metrics.get('rs_percentile', 0) if isinstance(metrics, dict) else 0
            html_content += f"""
                <tr>
                    <td><b>{symbol}</b></td>
                    <td>{rs_score:.2f}</td>
                    <td>{rs_pct:.2f}%</td>
                </tr>
            """
    else:
        html_content += """
            <tr>
                <td colspan="3" class="no-data">⏳ Relative Strength calculation in progress... Table will refresh automatically.</td>
            </tr>
        """
        
    html_content += """
        </table>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


def generate_totp_token(totp_secret: str) -> str:
    """Generates time-based 6-digit OTP for SmartAPI authentication."""
    if not totp_secret:
        raise ValueError("SMARTAPI_TOTP secret is not provided in environment variables.")
    return pyotp.TOTP(totp_secret).now()


def initialize_smart_api_session():
    """Logs into Angel One SmartAPI and returns auth_token and feed_token."""
    logger.info("Initializing Angel One SmartAPI Session...")
    
    if not SMARTAPI_KEY or not SMARTAPI_CLIENT or not SMARTAPI_TOTP:
        logger.error("Missing critical environment variables: SMARTAPI_KEY, SMARTAPI_CLIENT, or SMARTAPI_TOTP")
        return None, None

    try:
        smart_conn = SmartConnect(api_key=SMARTAPI_KEY)
        totp = generate_totp_token(SMARTAPI_TOTP)
        
        session_data = smart_conn.generateSession(SMARTAPI_CLIENT, SMARTAPI_PIN, totp)
        
        if not session_data.get("status"):
            logger.error(f"SmartAPI Authentication Failed: {session_data}")
            return None, None

        auth_token = session_data["data"]["jwtToken"]
        feed_token = smart_conn.getfeedToken()
        
        logger.info("SmartAPI Session Authenticated Successfully.")
        return auth_token, feed_token

    except Exception as e:
        logger.error(f"Exception during SmartAPI login: {e}")
        return None, None


def start_websocket_bg(auth_token, feed_token):
    """Runs WebSocket connection in a background thread."""
    try:
        stream_manager = SmartStreamManager()
        stream_manager.start_stream(auth_token, feed_token)
    except Exception as e:
        logger.error(f"WebSocket Thread Exception: {e}")


def run_scanner_bg():
    """Runs Relative Strength engine periodically in background with fail-safe error handling."""
    global LATEST_ANALYSIS_RESULTS
    rs_engine = RelativeStrengthEngine(benchmark_symbol="^NSEI")
    
    while True:
        try:
            logger.info("Executing Quant Scan Engine...")
            results = rs_engine.evaluate_universe(symbols=None)
            if results:
                LATEST_ANALYSIS_RESULTS = results
                logger.info(f"RS Scan completed. {len(LATEST_ANALYSIS_RESULTS)} stocks updated in cache.")
            else:
                logger.warning("RS Scan returned empty results. Retaining existing cache.")
        except Exception as e:
            logger.error(f"Error during RS background scan: {e}")
        time.sleep(300)  # Re-scan every 5 minutes


def main():
    logger.info("==========================================")
    logger.info("  STARTING VMS PRO V4 WEB & QUANT ENGINE")
    logger.info("==========================================")

    # Step 1: Authenticate SmartAPI
    auth_token, feed_token = initialize_smart_api_session()

    # Step 2: Start WebSocket Stream in Background Thread
    if auth_token and feed_token:
        logger.info("Starting SmartAPI WebSocket live feed in background thread...")
        ws_thread = threading.Thread(target=start_websocket_bg, args=(auth_token, feed_token), daemon=True)
        ws_thread.start()

    # Step 3: Start Relative Strength Scanner in Background Thread
    scanner_thread = threading.Thread(target=run_scanner_bg, daemon=True)
    scanner_thread.start()

    # Step 4: Start FastAPI Web Server on Dynamic Render Port
    render_port = int(os.getenv("PORT", PORT))
    logger.info(f"Starting Web Dashboard at http://{HOST}:{render_port}/dashboard")
    uvicorn.run(app, host=HOST, port=render_port)


if __name__ == "__main__":
    main()