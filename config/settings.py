import os

# Angel One SmartAPI Credentials
SMARTAPI_KEY = os.getenv("SMARTAPI_KEY", "")
SMARTAPI_CLIENT = os.getenv("SMARTAPI_CLIENT", "")
SMARTAPI_PIN = os.getenv("SMARTAPI_PIN", "")
SMARTAPI_TOTP = os.getenv("SMARTAPI_TOTP", "")

# Server Configuration
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 10000))

# Sample Watchlist Fallback if not configured elsewhere
WATCHLIST = [
    "RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "BHARTIARTL.NS", "SBIN.NS", "LTIM.NS", "TATAMOTORS.NS", "WIPRO.NS"
]