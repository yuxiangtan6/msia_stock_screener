import requests
from bs4 import BeautifulSoup
import re
import time
from stock_list import STOCK_UNIVERSE

def fetch_klse_data(code):
    """从klsescreener抓取单只股票的行业分类和市值"""
    url = f"https://www.klsescreener.com/v2/stocks/view/{code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")

        # 找 "Main Market : Banking" 这种格式的行业信息
        sector_match = re.search(
    r'(Main Market|Ace Market|LEAP Market)\s*:\s*([A-Za-z0-9 &,\-\']+?)(?=\s{2,}|\s+Close)',
    text,
    re.IGNORECASE
)
        board = sector_match.group(1) if sector_match else None
        sector = sector_match.group(2).strip() if sector_match else None

        # 找市值
        cap_match = re.search(r'Market Cap\s+([\d,.]+[BMK]?)', text)
        market_cap = cap_match.group(1) if cap_match else None

        return board, sector, market_cap
    except Exception as e:
        return None, None, f"错误: {e}"

# 只测试前100只
test_tickers = list(STOCK_UNIVERSE.keys())[:100]

results = []
success_count = 0
for ticker in test_tickers:
    code = ticker.replace(".KL", "")
    board, sector, cap = fetch_klse_data(code)
    status = "✅" if sector else "❌"
    if sector:
        success_count += 1
    print(f"{status} {code}: 板块={board}, 行业={sector}, 市值={cap}")
    results.append((ticker, board, sector, cap))
    time.sleep(1)  # 礼貌性延迟，别把免费网站打崩

print(f"\n===== 测试结果 =====")
print(f"成功抓到行业分类: {success_count}/{len(test_tickers)}")