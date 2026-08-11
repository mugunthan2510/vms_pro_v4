import pandas as pd

class PivotEngine:
    """VMS PRO v4.0 - Monthly Pivot Strategy Engine"""

    def calculate_score(self, df_daily: pd.DataFrame, df_monthly: pd.DataFrame) -> dict:
        """
        df_daily: Daily OHLCV data
        df_monthly: Resampled Monthly OHLCV data
        """
        if df_daily.empty or len(df_monthly) < 4:
            return {"score": 0, "monthly_pivot": 0, "day1_high": 0, "details": "Insufficient Data"}

        score = 0
        
        # --- 1. MONTHLY PIVOT TREND CHECK (Max 10 pts) ---
        # Pivot = (H + L + C) / 3
        df_monthly['Pivot'] = (df_monthly['High'] + df_monthly['Low'] + df_monthly['Close']) / 3.0
        
        curr_p = df_monthly['Pivot'].iloc[-1]
        p_1 = df_monthly['Pivot'].iloc[-2]
        p_2 = df_monthly['Pivot'].iloc[-3]
        p_3 = df_monthly['Pivot'].iloc[-4]
        
        greater_than_count = sum([curr_p > p_1, curr_p > p_2, curr_p > p_3])
        
        if greater_than_count == 3:
            pivot_trend_score = 10
        elif greater_than_count == 2:
            pivot_trend_score = 8
        elif greater_than_count == 1:
            pivot_trend_score = 5
        else:
            pivot_trend_score = 0
            
        score += pivot_trend_score

        # --- 2. PRICE ABOVE CURRENT MONTH PIVOT (Max 5 pts) ---
        curr_price = df_daily['Close'].iloc[-1]
        price_above_pivot = curr_price > curr_p
        if price_above_pivot:
            score += 5

        # --- 3. DAY-1 HIGH BREAKOUT (Max 10 pts) ---
        current_month = df_daily.index[-1].month
        current_month_df = df_daily[df_daily.index.month == current_month]
        
        day1_high = current_month_df['High'].iloc[0] if not current_month_df.empty else 0
        day1_breakout = curr_price > day1_high
        
        if day1_breakout:
            score += 10

        # --- 4. RETEST CONFIRMATION (Max 5 pts) ---
        retest_success = False
        if len(current_month_df) > 2 and day1_breakout:
            recent_lows = current_month_df['Low'].iloc[1:]
            if any(abs(low - day1_high) / day1_high < 0.01 for low in recent_lows if day1_high > 0):
                retest_success = True
                score += 5

        return {
            "score": score,
            "monthly_pivot": round(curr_p, 2),
            "day1_high": round(day1_high, 2),
            "price_above_pivot": price_above_pivot,
            "day1_breakout": day1_breakout,
            "retest_success": retest_success
        }