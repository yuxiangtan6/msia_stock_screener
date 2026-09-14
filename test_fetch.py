import yfinance as yf

# Maybank 的股票代码
ticker = "1155.KL"

# 抓取过去6个月的历史价格数据
data = yf.download(ticker, period="6mo")

print(f"抓取到 {ticker} 的数据：")
print(data.tail(10))  # 打印最近10天的数据
print(f"\n一共有 {len(data)} 天的数据")