import yfinance as yf
import time
from stock_list import STOCK_UNIVERSE

print(f"准备测试 {len(STOCK_UNIVERSE)} 只股票...\n")

success_list = []
fail_list = []

for ticker, sector in STOCK_UNIVERSE.items():
    try:
        data = yf.download(ticker, period="1mo", auto_adjust=False, progress=False)
        if data.empty or len(data) < 5:
            print(f"❌ {ticker} ({sector}) — 数据为空或太少")
            fail_list.append(ticker)
        else:
            last_close = data['Close'].iloc[-1].item()
            print(f"✅ {ticker} ({sector}) — 最新收盘价: {last_close:.2f}")
            success_list.append(ticker)
    except Exception as e:
        print(f"❌ {ticker} ({sector}) — 出错: {e}")
        fail_list.append(ticker)

    time.sleep(0.3)  # 稍微停顿，避免请求太快被限制

print(f"\n===== 测试结果 =====")
print(f"成功: {len(success_list)} 只")
print(f"失败: {len(fail_list)} 只")
if fail_list:
    print(f"\n失败的代码：{fail_list}")