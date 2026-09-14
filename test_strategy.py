import yfinance as yf
import pandas as pd

# ============ 参数（跟Pine Script保持一致）============
TICKER = "1155.KL"
EMA_LEN = 30
SMA_LEN = 10
EMA_SLOPE_LOOKBACK = 5
EXTENSION_PCT = 5.0
LOOKBACK_BARS = 20
TOUCH_TOLERANCE_PCT = 1.5
SUPPORT_BREAK_PCT = 1.0
MAX_BARS_AFTER_SUPPORT = 10
STOP_BUFFER_PCT = 0.5

# ============ 抓取数据 ============
data = yf.download(TICKER, period="1y", auto_adjust=False)
data.columns = data.columns.get_level_values(0)  # 去掉多层列名
data = data.reset_index()

# ============ 计算均线 ============
data["EMA30"] = data["Close"].ewm(span=EMA_LEN, adjust=False).mean()
data["SMA10"] = data["Close"].rolling(window=SMA_LEN).mean()
data["EMA_Rising"] = data["EMA30"] > data["EMA30"].shift(EMA_SLOPE_LOOKBACK)

# ============ 阶段1: 检测拉伸 ============
data["Extension"] = (data["Close"] - data["EMA30"]) / data["EMA30"] * 100
data["Is_Extended"] = data["Extension"] >= EXTENSION_PCT

# 记录"最近一次拉伸"发生的行号
extended_idx = pd.Series(index=data.index, dtype="float64")
last_extended = None
for i in range(len(data)):
    if data["Is_Extended"].iloc[i]:
        last_extended = i
    extended_idx.iloc[i] = last_extended
data["Last_Extended_Idx"] = extended_idx

# ============ 阶段2: 检测回踩获得支撑 ============
data["Near_EMA"] = (abs(data["Low"] - data["EMA30"]) / data["EMA30"] * 100) <= TOUCH_TOLERANCE_PCT
data["Holds_Above"] = data["Close"] >= data["EMA30"] * (1 - SUPPORT_BREAK_PCT / 100)
data["Valid_Support_Window"] = (
    data["Last_Extended_Idx"].notna() &
    ((data.index - data["Last_Extended_Idx"]) <= LOOKBACK_BARS)
)
data["Support_Touch"] = data["Valid_Support_Window"] & data["Near_EMA"] & data["Holds_Above"]

# 记录"最近一次回踩支撑"发生的行号和当时的低点
support_idx = pd.Series(index=data.index, dtype="float64")
support_low = pd.Series(index=data.index, dtype="float64")
last_support_idx = None
last_support_low = None
for i in range(len(data)):
    if data["Support_Touch"].iloc[i]:
        last_support_idx = i
        last_support_low = data["Low"].iloc[i]
    support_idx.iloc[i] = last_support_idx
    support_low.iloc[i] = last_support_low
data["Last_Support_Idx"] = support_idx
data["Support_Low"] = support_low

# ============ 阶段3: 重新升穿SMA10，确认信号 ============
data["Cross_Up"] = (data["Close"] > data["SMA10"]) & (data["Close"].shift(1) <= data["SMA10"].shift(1))
data["Valid_Entry_Window"] = (
    data["Last_Support_Idx"].notna() &
    ((data.index - data["Last_Support_Idx"]) <= MAX_BARS_AFTER_SUPPORT)
)

data["Entry_Signal"] = (
    data["Cross_Up"] &
    data["Valid_Entry_Window"] &
    data["EMA_Rising"] &
    (data["Close"] > data["EMA30"])
)

# ============ 止损参考位 ============
data["Stop_Level"] = data["Support_Low"] * (1 - STOP_BUFFER_PCT / 100)

# ============ 输出结果 ============
print(f"\n{TICKER} 最近30天数据检查：")
print(data[["Date", "Close", "EMA30", "SMA10", "Is_Extended", "Support_Touch", "Entry_Signal"]].tail(30).to_string())

print(f"\n过去1年触发的入场信号：")
signals = data[data["Entry_Signal"]]
print(signals[["Date", "Close", "EMA30", "SMA10", "Stop_Level"]].to_string())

print(f"\n2026年3月附近的数据检查：")
march_check = data[(data["Date"] >= "2026-03-10") & (data["Date"] <= "2026-03-20")]
print(march_check[["Date", "Close", "EMA30", "SMA10", "Is_Extended", "Support_Touch", "Entry_Signal"]].to_string())