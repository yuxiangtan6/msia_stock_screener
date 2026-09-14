import requests
from bs4 import BeautifulSoup
import re
import time
import json
from stock_list import STOCK_UNIVERSE

def fetch_klse_data(code):
    """从klsescreener抓取单只股票的行业分类和市值"""
    url = f"https://www.klsescreener.com/v2/stocks/view/{code}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        text = BeautifulSoup(resp.text, "html.parser").get_text(separator=" ")

        sector_match = re.search(
            r'(Main Market|Ace Market|LEAP Market)\s*:\s*([A-Za-z0-9 &,\-\']+?)(?=\s{2,}|\s+Close)',
            text,
            re.IGNORECASE
        )
        board = sector_match.group(1) if sector_match else None
        sector = sector_match.group(2).strip() if sector_match else None

        cap_match = re.search(r'Market Cap\s+([\d,.]+[BMK]?)', text)
        market_cap = cap_match.group(1) if cap_match else None

        return board, sector, market_cap
    except Exception as e:
        return None, None, f"错误: {e}"

# 全部股票
all_tickers = list(STOCK_UNIVERSE.keys())
total = len(all_tickers)

results = []
success_count = 0
fail_list = []

print(f"开始抓取 {total} 只股票的行业+市值数据...\n")

for i, ticker in enumerate(all_tickers, 1):
    code = ticker.replace(".KL", "")
    board, sector, cap = fetch_klse_data(code)
    status = "✅" if sector else "❌"
    if sector:
        success_count += 1
    else:
        fail_list.append(ticker)

    print(f"[{i}/{total}] {status} {code}: 板块={board}, 行业={sector}, 市值={cap}")
    results.append((ticker, board, sector, cap))
    time.sleep(1)

    # 每跑100只，先保存一次进度，避免中途断了全白跑
    if i % 100 == 0:
        output = {t: {"board": b, "sector": s, "market_cap": c} for t, b, s, c in results}
        with open("klse_sector_data.json", "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n--- 已保存进度：{i}/{total} ---\n")

# 最终完整保存
output = {t: {"board": b, "sector": s, "market_cap": c} for t, b, s, c in results}
with open("klse_sector_data.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n===== 全部完成 =====")
print(f"成功: {success_count}/{total}")
print(f"失败: {len(fail_list)} 只")
if fail_list:
    print(f"失败清单: {fail_list}")
print(f"\n✅ 已保存到 klse_sector_data.json")