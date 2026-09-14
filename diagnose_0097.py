import yfinance as yf
import pandas as pd

TICKER = "0097.KL"
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
data = data[data["Volume"] > 0].reset_index(drop=True)

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
data["Bars_Since_Extension"] = data.index - data["Last_Extended_Idx"]

data["Near_EMA"] = (abs(data["Close"] - data["EMA30"]) / data["EMA30"] * 100) <= TOUCH_TOLERANCE_PCT
data["Holds_Above"] = data["Close"] >= data["EMA30"] * (1 - SUPPORT_BREAK_PCT / 100)
data["Valid_Support_Window"] = (
    data["Last_Extended_Idx"].notna() &
    (data["Bars_Since_Extension"] > 0) &
    (data["Bars_Since_Extension"] <= LOOKBACK_BARS)
)
data["Support_Touch"] = data["Valid_Support_Window"] & data["Near_EMA"] & data["Holds_Above"]

support_idx = pd.Series(index=data.index, dtype="float64")
last_support_idx = None
for i in range(len(data)):
    if data["Support_Touch"].iloc[i]:
        last_support_idx = i
    support_idx.iloc[i] = last_support_idx
data["Last_Support_Idx"] = support_idx

data["Cross_Up"] = (data["Close"] > data["SMA10"]) & (data["Close"].shift(1) <= data["SMA10"].shift(1))
data["Valid_Entry_Window"] = (
    data["Last_Support_Idx"].notna() &
    ((data.index - data["Last_Support_Idx"]) <= MAX_BARS_AFTER_SUPPORT)
)
data["Entry_Signal"] = (
    data["Cross_Up"] & data["Valid_Entry_Window"] &
    data["EMA_Rising"] & (data["Close"] > data["EMA30"])
)

print("===== 过去30天详细数据 =====")
print(data[["Date", "Close", "EMA30", "SMA10", "Support_Touch", "Cross_Up", "Entry_Signal"]].tail(30).to_string())

print("\n===== 过去一年所有Entry_Signal触发日 =====")
signals = data[data["Entry_Signal"]]
print(signals[["Date", "Close"]].to_string())