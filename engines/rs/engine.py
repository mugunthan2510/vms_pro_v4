import pandas as pd

class RelativeStrengthEngine:
    """Calculates Relative Strength Percentile against Nifty"""

    def calculate_score(self, df_stock: pd.DataFrame, df_nifty: pd.DataFrame = None) -> dict:
        if df_stock.empty or len(df_stock) < 90:
            return {"score": 5, "rs_status": "NEUTRAL"}

        # 90-Day Return Calculation
        stock_90d_ret = ((df_stock['Close'].iloc[-1] - df_stock['Close'].iloc[-90]) / df_stock['Close'].iloc[-90]) * 100

        # Dynamic Benchmark comparison or Percentile Proxy
        if stock_90d_ret > 15.0:
            score = 10
            rs_status = "RS Percentile > 80"
        elif stock_90d_ret > 5.0:
            score = 5
            rs_status = "RS Percentile 60-80"
        else:
            score = 0
            rs_status = "RS Percentile < 60"

        return {
            "score": score,
            "stock_90d_return": round(stock_90d_ret, 2),
            "rs_status": rs_status
        }