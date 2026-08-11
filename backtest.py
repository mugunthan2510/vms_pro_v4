import warnings
warnings.filterwarnings('ignore')

import yfinance as yf
import pandas as pd
import numpy as np

def calculate_rs(df, index_df):
    """Calculates Relative Strength against Nifty 50."""
    stock_ret = df['Close'].pct_change(21)
    index_ret = index_df['Close'].pct_change(21)
    rs = stock_ret - index_ret
    return rs

def backtest_vms_pro_v4(symbol: str, index_df: pd.DataFrame, start_date: str, end_date: str, initial_capital=100000):
    df = yf.download(symbol, start=start_date, end=end_date, interval="1d", auto_adjust=True, progress=False)
    if df.empty or len(df) < 80:
        return None

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Technical Indicators
    df['20_SMA'] = df['Close'].rolling(20).mean()
    df['50_SMA'] = df['Close'].rolling(50).mean()
    df['200_SMA'] = df['Close'].rolling(200).mean()
    df['Vol_20SMA'] = df['Volume'].rolling(20).mean()
    
    # ATR Calculation
    high_low = df['High'] - df['Low']
    high_close = (df['High'] - df['Close'].shift()).abs()
    low_close = (df['Low'] - df['Close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()

    # Relative Strength vs Index
    df['RS'] = calculate_rs(df, index_df)
    df['RS_Rank'] = df['RS'].rolling(100).rank(pct=True) * 100

    # Monthly CPR Calculation
    df['Prev_Month_High'] = df['High'].shift(20)
    df['Prev_Month_Low'] = df['Low'].shift(20)
    df['Prev_Month_Close'] = df['Close'].shift(20)
    df['Monthly_Pivot'] = (df['Prev_Month_High'] + df['Prev_Month_Low'] + df['Prev_Month_Close']) / 3

    # STRICT VMS PRO V4 CONFLUENCE CONDITIONS (Score >= 80)
    c1 = df['Close'] > df['Monthly_Pivot']        # Above Monthly Pivot
    c2 = df['Close'] > df['20_SMA']               # Short Term Trend
    c3 = df['20_SMA'] > df['50_SMA']              # Medium Term Trend Alignment
    c4 = df['Close'] > df['200_SMA']              # Macro Bullish Regime
    c5 = df['Volume'] > 1.5 * df['Vol_20SMA']     # Institutional Volume Surge
    c6 = df['RS_Rank'] >= 70                      # High Outperformance vs Nifty

    df['Valid_Signal'] = c1 & c2 & c3 & c4 & c5 & c6

    trades = []
    in_position = False
    entry_price = 0
    stop_loss = 0
    target_1 = 0
    capital = initial_capital
    risk_per_trade = 0.01

    for i in range(1, len(df)):
        date = df.index[i]
        price = df['Close'].iloc[i]
        atr = df['ATR'].iloc[i-1]

        if in_position:
            high_price = df['High'].iloc[i]
            low_price = df['Low'].iloc[i]

            # Trailing SL Adjustment (Move SL to Breakeven after T1)
            if high_price >= target_1 and stop_loss < entry_price:
                stop_loss = entry_price # Move to Breakeven

            # Stop Loss / Trailing Hit
            if low_price <= stop_loss:
                pnl = (stop_loss - entry_price) * qty
                capital += pnl
                result_type = 'BREAKEVEN' if stop_loss == entry_price else 'STOP_LOSS'
                trades.append({
                    'symbol': symbol, 'entry_date': entry_date, 'exit_date': date,
                    'entry_price': round(entry_price, 2), 'exit_price': round(stop_loss, 2),
                    'pnl': round(pnl, 2),
                    'return_pct': round((stop_loss - entry_price) / entry_price * 100, 2),
                    'result': result_type
                })
                in_position = False

            # Target 2 (1:2.5 Risk-Reward Exit)
            elif high_price >= target_2:
                pnl = (target_2 - entry_price) * qty
                capital += pnl
                trades.append({
                    'symbol': symbol, 'entry_date': entry_date, 'exit_date': date,
                    'entry_price': round(entry_price, 2), 'exit_price': round(target_2, 2),
                    'pnl': round(pnl, 2),
                    'return_pct': round((target_2 - entry_price) / entry_price * 100, 2),
                    'result': 'TARGET_HIT'
                })
                in_position = False

        # Entry Check
        elif df['Valid_Signal'].iloc[i-1] and not in_position and not np.isnan(atr):
            entry_price = price
            entry_date = date
            risk_amt = capital * risk_per_trade
            sl_dist = 1.5 * atr
            stop_loss = entry_price - sl_dist
            target_1 = entry_price + (1.5 * sl_dist)
            target_2 = entry_price + (2.5 * sl_dist)

            qty = int(risk_amt / sl_dist) if sl_dist > 0 else 0
            if qty > 0:
                in_position = True

    return pd.DataFrame(trades)

if __name__ == "__main__":
    print("⏳ Downloading Nifty 50 Index benchmark data...")
    nifty = yf.download("^NSEI", start="2023-01-01", end="2026-08-01", auto_adjust=True, progress=False)
    if isinstance(nifty.columns, pd.MultiIndex):
        nifty.columns = nifty.columns.get_level_values(0)

    symbols = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HEROMOTOCO.NS", "ICICIBANK.NS", "WIPRO.NS", "DLF.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"]
    all_trades = []

    print("📊 Running Refined VMS PRO v4.0 Institutional Backtest...")
    for sym in symbols:
        df_t = backtest_vms_pro_v4(sym, nifty, "2023-01-01", "2026-08-01")
        if df_t is not None and not df_t.empty:
            all_trades.append(df_t)

    if all_trades:
        results = pd.concat(all_trades, ignore_index=True)
        wins = len(results[results['pnl'] > 0])
        total_trades = len(results)
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        total_pnl = results['pnl'].sum()

        print("\n================ REFINED BACKTEST SUMMARY ================")
        print(f"Total Quality Trades : {total_trades}")
        print(f"Win Rate             : {win_rate:.2f}%")
        print(f"Total Profit (INR)   : ₹{total_pnl:,.2f}")
        print("==========================================================")
        print(results.tail(10))