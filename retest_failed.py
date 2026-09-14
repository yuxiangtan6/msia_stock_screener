import yfinance as yf
import time

failed = ['0041.KL','03008.KL','03017.KL','03029.KL','03037.KL','03042.KL',
          '03043.KL','03045.KL','03056.KL','0469.KL','4219.KL','6742.KL','9776.KL']

for t in failed:
    try:
        data = yf.download(t, period='1mo', auto_adjust=False, progress=False)
        if data.empty:
            print(f"❌ {t} 仍然失败（空数据）")
        else:
            print(f"✅ {t} 这次成功了！最新价: {data['Close'].iloc[-1].item():.3f}")
    except Exception as e:
        print(f"❌ {t} 出错: {e}")
    time.sleep(1)