import json
from collections import Counter

with open("klse_sector_data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

sectors = [v["sector"] for v in data.values() if v.get("sector")]
sector_counts = Counter(sectors)

print(f"一共有 {len(sector_counts)} 个行业分类\n")
print(f"{'行业':<45} {'公司数量'}")
print("-" * 55)
for sector, count in sector_counts.most_common():
    print(f"{sector:<45} {count}")