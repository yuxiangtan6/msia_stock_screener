import yfinance as yf
import pandas as pd

TICKER = "5183.KL"
EMA_LEN = 30
SMA_LEN = 10
EMA_SLOPE_LOOKBACK = 5
EXTENSION_PCT = 5.0
LOOKBACK_BARS = 20
TOUCH_TOLERANCE_PCT = 1.5
SUPPORT_BREAK_PCT = 1.0
MAX_BARS_AFTER_SUPPORT = 10

data = yf.download(TICKER, period="1y", auto_adjust=False, progress=False)
data.columns = data.columns.get_level_values(0)
data = data.reset_index()

data["EMA30"] = data["Close"].ewm(span=EMA_LEN, adjust=False).mean()
data["SMA10"] = data["Close"].rolling(window=SMA_LEN).mean()
data["EMA_Rising"] = data["EMA30"] > data["EMA30"].shift(EMA_SLOPE_LOOKBACK)

data["Extension"] = (data["Close"] - data["EMA30"]) / data["EMA30"] * 100
data["Is_Extended"] = data["Extension"] >= EXTENSION_PCT

extended_idx = pd.Series(index=data.index, dtype="float64")
last_extended = None
for i in range(len(data)):
    if data["Is_Extended"].iloc[i]:
        last_extended = i
    extended_idx.iloc[i] = last_extended
data["Last_Extended_Idx"] = extended_idx

data["Near_EMA"] = (abs(data["Low"] - data["EMA30"]) / data["EMA30"] * 100) <= TOUCH_TOLERANCE_PCT
data["Holds_Above"] = data["Close"] >= data["EMA30"] * (1 - SUPPORT_BREAK_PCT / 100)
data["Valid_Support_Window"] = (
    data["Last_Extended_Idx"].notna() &
    ((data.index - data["Last_Extended_Idx"]) <= LOOKBACK_BARS)
)
data["Support_Touch"] = data["Valid_Support_Window"] & data["Near_EMA"] & data["Holds_Above"]

# ============ 打印所有"拉伸"事件 ============
print("===== 所有触发'拉伸'(Is_Extended)的日期 =====")
extended_events = data[data["Is_Extended"]]
print(extended_events[["Date", "Close", "EMA30", "Extension"]].to_string())

# ============ 打印所有"回踩支撑"事件，并附上它引用的是哪一次拉伸 ============
print("\n===== 所有触发'回踩支撑'(Support_Touch)的日期，及对应的拉伸日期 =====")
support_events = data[data["Support_Touch"]].copy()
support_events["对应拉伸日期"] = support_events["Last_Extended_Idx"].apply(
    lambda idx: data.loc[int(idx), "Date"] if pd.notna(idx) else None
)
print(support_events[["Date", "Close", "Low", "EMA30", "对应拉伸日期"]].to_string())

# ============ 最新一天的状态 ============
print("\n===== 最新一天状态 =====")
latest = data.iloc[-1]
print(f"日期: {latest['Date']}")
print(f"Close: {latest['Close']:.3f}, EMA30: {latest['EMA30']:.3f}, EMA_Rising: {latest['EMA_Rising']}")
print(f"最新Support_Low对应的支撑日期: {data.loc[int(data.iloc[-1]['Last_Support_Idx']), 'Date'] if pd.notna(data.iloc[-1].get('Last_Support_Idx', None)) else '无'}")