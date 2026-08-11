import pandas as pd

class TrendEngine:
    """Calculates Daily & Weekly EMA Trend Alignment (20, 50, 200 EMA)"""

    def calculate_score(self, df_daily: pd.DataFrame) -> dict:
        if df_daily.empty or len(df_daily) < 200:
            return {"score": 5, "trend": "MIXED"}

        close = df_daily['Close']
        ema_20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
        ema_50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        ema_200 = close.ewm(span=200, adjust=False).mean().iloc[-1]
        curr_price = close.iloc[-1]

        # Strong Uptrend: Price > EMA20 > EMA50 > EMA200
        strong_uptrend = curr_price > ema_20 and ema_20 > ema_50 and ema_50 > ema_200

        if strong_uptrend:
            score = 10
            status = "STRONG UPTREND"
        elif curr_price > ema_20 and ema_20 > ema_50:
            score = 5
            status = "MIXED TREND"
        else:
            score = 0
            status = "WEAK/DOWNTREND"

        return {
            "score": score,
            "trend": status,
            "ema_20": round(ema_20, 2),
            "ema_50": round(ema_50, 2),
            "ema_200": round(ema_200, 2)
        }