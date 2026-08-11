import pandas as pd

class SMCEngine:
    """Calculates SMC Concepts (FVG, Liquidity Sweep, Order Block) & Sector Alignment"""
    
    def calculate_score(self, df: pd.DataFrame, sector_rank: int = 1) -> dict:
        if df.empty or len(df) < 5:
            return {"score": 0, "smc_score": 0, "sector_score": 0, "details": "Insufficient Data"}
        
        smc_score = 0
        
        # 1. Fair Value Gap (FVG) Check (Bullish FVG: Low of candle 3 > High of candle 1)
        c1_high = df['High'].iloc[-3]
        c3_low = df['Low'].iloc[-1]
        fvg_present = c3_low > c1_high
        
        # 2. Liquidity Sweep Check (Current low broke prev low but closed higher)
        prev_low = df['Low'].iloc[-2]
        curr_low = df['Low'].iloc[-1]
        curr_close = df['Close'].iloc[-1]
        liquidity_sweep = (curr_low < prev_low) and (curr_close > prev_low)
        
        # 3. Order Block & BOS (Break of Structure)
        recent_high = df['High'].iloc[-10:-1].max() if len(df) >= 10 else df['High'].max()
        bos_present = curr_close > recent_high
        
        indicators_count = sum([fvg_present, liquidity_sweep, bos_present])
        
        if indicators_count >= 3:
            smc_score = 10
        elif indicators_count >= 1:
            smc_score = 5
        else:
            smc_score = 0
            
        # Sector Score Logic
        if sector_rank <= 3:
            sector_score = 10
        elif sector_rank <= 5:
            sector_score = 5
        else:
            sector_score = 0
            
        return {
            "smc_score": smc_score,
            "sector_score": sector_score,
            "fvg": fvg_present,
            "liquidity_sweep": liquidity_sweep,
            "bos": bos_present
        }