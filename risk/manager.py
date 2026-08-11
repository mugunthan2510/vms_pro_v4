import pandas as pd

class RiskManager:
    """VMS PRO v4.0 Risk Management & Position Sizing Engine"""

    def calculate_risk_parameters(self, df: pd.DataFrame, capital: float = 100000.0, risk_pct: float = 0.01) -> dict:
        if df.empty or len(df) < 14:
            return {"valid_setup": False, "reason": "Insufficient ATR Data"}

        # Calculate 14-period ATR
        high_low = df['High'] - df['Low']
        high_cp = abs(df['High'] - df['Close'].shift(1))
        low_cp = abs(df['Low'] - df['Close'].shift(1))
        tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]

        curr_price = df['Close'].iloc[-1]
        stop_loss_distance = 1.5 * atr
        stop_loss_price = round(curr_price - stop_loss_distance, 2)

        # Targets
        target_1 = round(curr_price + (stop_loss_distance * 1.5), 2)
        target_2 = round(curr_price + (stop_loss_distance * 2.5), 2)
        target_3 = round(curr_price + (stop_loss_distance * 4.0), 2)

        # Position Sizing based on 1% Risk per Trade
        risk_amount = capital * risk_pct
        quantity = int(risk_amount / stop_loss_distance) if stop_loss_distance > 0 else 0

        return {
            "valid_setup": True if quantity > 0 else False,
            "atr": round(atr, 2),
            "stop_loss": stop_loss_price,
            "target_1": target_1,
            "target_2": target_2,
            "target_3": target_3,
            "position_size": quantity,
            "risk_per_trade": risk_amount
        }