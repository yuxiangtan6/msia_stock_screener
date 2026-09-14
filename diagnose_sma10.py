import yfinance as yf

TICKER = "2291.KL"
data = yf.download(TICKER, period="1y", auto_adjust=False, progress=False)
data.columns = data.columns.get_level_values(0)
data = data.reset_index()
data = data[data["Volume"] > 0].reset_index(drop=True)

# 找到9月1日的位置，往前推10天（构成SMA10的窗口）
target_date = "2026-09-01"
target_idx = data[data["Date"] == target_date].index[0]

window = data.iloc[target_idx - 9 : target_idx + 1]  # 含9月1日在内的10天
print(f"构成 {target_date} SMA10 的10天原始收盘价：")
print(window[["Date", "Close"]].to_string())
print(f"\n手动计算平均值: {window['Close'].mean():.4f}")