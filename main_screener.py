import yfinance as yf
import pandas as pd
import time
import json
import os
from datetime import datetime
from stock_list import STOCK_UNIVERSE

# ============ 策略参数（跟Pine Script保持一致）============
EMA_LEN = 30
SMA_LEN = 10
EMA_SLOPE_LOOKBACK = 5
EXTENSION_PCT = 5.0
LOOKBACK_BARS = 20
TOUCH_TOLERANCE_PCT = 2.0
SUPPORT_BREAK_PCT = 1.0
MAX_BARS_AFTER_SUPPORT = 10
STOP_BUFFER_PCT = 0.5
SUPPORT_INVALID_PCT = 1.0
RECENT_BREAKOUT_LOOKBACK = 10

# ============ 加载KLSE行业/市值数据 ============
with open("klse_sector_data.json", "r", encoding="utf-8") as f:
    KLSE_DATA = json.load(f)


def parse_market_cap_str(cap_str):
    """把 '125.6B' / '421.7M' / '8,746.3M' 这种格式转成实际数字"""
    if not cap_str:
        return None
    cap_str = cap_str.replace(",", "").strip()
    try:
        if cap_str.endswith("B"):
            return float(cap_str[:-1]) * 1e9
        elif cap_str.endswith("M"):
            return float(cap_str[:-1]) * 1e6
        elif cap_str.endswith("K"):
            return float(cap_str[:-1]) * 1e3
        else:
            return float(cap_str)
    except ValueError:
        return None


def compute_signals(ticker, max_retries=3):
    """抓取数据并计算策略信号，返回最新一行的关键信息，失败返回None"""
    data = None
    for attempt in range(max_retries):
        try:
            data = yf.download(ticker, period="1y", auto_adjust=False, progress=False)
            if not data.empty and len(data) >= EMA_LEN + LOOKBACK_BARS:
                break
            data = None
        except Exception:
            data = None
        if data is None and attempt < max_retries - 1:
            time.sleep(1.5)

    if data is None:
        return None

    try:
        data.columns = data.columns.get_level_values(0)
        data = data.reset_index()
        data = data[data["Volume"] > 0].reset_index(drop=True)
        if len(data) < EMA_LEN + LOOKBACK_BARS:
            return None

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

        data["Cross_Up"] = (data["Close"] > data["SMA10"]) & (data["Close"].shift(1) <= data["SMA10"].shift(1))
        data["Valid_Entry_Window"] = (
            data["Last_Support_Idx"].notna() &
            ((data.index - data["Last_Support_Idx"]) <= MAX_BARS_AFTER_SUPPORT)
        )
        data["Entry_Signal"] = (
            data["Cross_Up"] & data["Valid_Entry_Window"] &
            data["EMA_Rising"] & (data["Close"] > data["EMA30"])
        )

        # 检查过去10天内（不含今天）是否有过Entry_Signal
        recent_window = data.iloc[-(RECENT_BREAKOUT_LOOKBACK + 1):-1]
        recent_signals = recent_window[recent_window["Entry_Signal"]]

        recent_breakout = False
        breakout_date = None
        breakout_price = None
        days_ago = None
        if not recent_signals.empty:
            last_signal_row = recent_signals.iloc[-1]
            recent_breakout = True
            breakout_date = last_signal_row["Date"]
            breakout_price = last_signal_row["Close"]
            days_ago = len(data) - 1 - last_signal_row.name

        latest = data.iloc[-1]
        support_low_val = latest["Support_Low"]
        latest_sma10 = latest["SMA10"]

        # 判断支撑是否已经破位
        support_broken = False
        if pd.notna(support_low_val) and support_low_val > 0:
            support_broken = latest["Close"] < support_low_val * (1 - SUPPORT_INVALID_PCT / 100)

        already_above_sma10 = latest["Close"] > latest_sma10

        result = {
            "ticker": ticker,
            "close": latest["Close"],
            "volume": latest["Volume"],
            "ema30": latest["EMA30"],
            "entry_signal_today": bool(latest["Entry_Signal"]),
            "pending_stage2": bool(latest["Valid_Entry_Window"]) and not bool(latest["Entry_Signal"]) and not support_broken and not already_above_sma10,
            "support_broken": support_broken,
            "support_low": support_low_val,
            "recent_breakout": recent_breakout and not bool(latest["Entry_Signal"]),
            "breakout_date": breakout_date,
            "breakout_price": breakout_price,
            "days_ago": days_ago,
        }
        result["pct_from_ema30"] = (result["close"] - result["ema30"]) / result["ema30"] * 100
        return result

    except Exception as e:
        print(f"⚠️ {ticker} 计算出错: {e}")
        return None


def format_number(n):
    if n is None or pd.isna(n):
        return "数据缺失"
    if n >= 1e9:
        return f"{n/1e9:.2f}B"
    elif n >= 1e6:
        return f"{n/1e6:.2f}M"
    return f"{n:,.0f}"


# ============ 主流程：跑完整个股票池 ============
print(f"开始扫描 {len(STOCK_UNIVERSE)} 只股票... {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

all_results = []
for ticker, (old_sector, company_name) in STOCK_UNIVERSE.items():
    result = compute_signals(ticker)
    if result:
        klse_info = KLSE_DATA.get(ticker, {})
        real_sector = klse_info.get("sector") or old_sector
        result["sector"] = real_sector
        result["board"] = klse_info.get("board", "—")
        result["company_name"] = company_name
        result["market_cap"] = parse_market_cap_str(klse_info.get("market_cap"))
        result["daily_trading_value"] = result["close"] * result["volume"]
        all_results.append(result)
        status = "🟢触发" if result["entry_signal_today"] else ("🟡等待中" if result["pending_stage2"] else "—")
        print(f"{ticker} ({result['sector']}) {status}")
    time.sleep(0.3)

# ============ 计算行业趋势（同行业股票中,收盘价在EMA30之上的比例）============
sector_trend = {}
all_sectors_present = set(r["sector"] for r in all_results if r["sector"])
for sector in all_sectors_present:
    sector_stocks = [r for r in all_results if r["sector"] == sector]
    above_count = sum(1 for r in sector_stocks if r["close"] > r["ema30"])
    total_count = len(sector_stocks)
    pct_above = above_count / total_count
    trend_label = "上升趋势" if pct_above > 0.5 else "偏弱/盘整"
    sector_trend[sector] = f"{trend_label} ({above_count}/{total_count})"

# ============ 计算大盘整体宽度 ============
market_above_count = sum(1 for r in all_results if r["close"] > r["ema30"])
market_total_count = len(all_results)
market_breadth_pct = market_above_count / market_total_count * 100

if market_breadth_pct > 60:
    market_verdict = "大盘偏强，可以相对积极"
    verdict_color = "#1a7a1a"
elif market_breadth_pct < 40:
    market_verdict = "大盘偏弱，建议保守，减少新仓位"
    verdict_color = "#cc0000"
else:
    market_verdict = "大盘中性，正常仓位"
    verdict_color = "#b8860b"

market_summary = f"{market_breadth_pct:.1f}% ({market_above_count}/{market_total_count} 只股票站上EMA30) — {market_verdict}"

# ============ 分组 ============
triggered = [r for r in all_results if r["entry_signal_today"]]
pending = [r for r in all_results if r["pending_stage2"]]
recent_breakout_list = [r for r in all_results if r["recent_breakout"]]

print(f"\n今日触发信号: {len(triggered)} 只")
print(f"等待突破中: {len(pending)} 只")

# ============ 生成HTML网页 ============
def build_table_rows(stock_list, show_breakout_info=False):
    rows = ""
    for r in stock_list:
        pct = f"{r['pct_from_ema30']:.2f}%" if r["pct_from_ema30"] is not None else "—"
        extra_cols = ""
        if show_breakout_info:
            breakout_date_str = r["breakout_date"].strftime("%Y-%m-%d") if r["breakout_date"] is not None else "—"
            pct_since_breakout = ((r["close"] - r["breakout_price"]) / r["breakout_price"] * 100) if r["breakout_price"] else None
            pct_since_str = f"{pct_since_breakout:.2f}%" if pct_since_breakout is not None else "—"
            date_sort_val = r["breakout_date"].strftime("%Y%m%d") if r["breakout_date"] is not None else "0"
            extra_cols = f'<td data-sort="{date_sort_val}">{breakout_date_str}</td><td data-sort="{r["days_ago"]}">{r["days_ago"]}天前</td><td data-sort="{pct_since_breakout if pct_since_breakout is not None else -9999}">{pct_since_str}</td>'
        rows += f"""
        <tr>
            <td>{r['ticker']}</td>
            <td>{r['company_name']}</td>
            <td>{r['sector']}</td>
            <td data-sort="{r['close']}">{r['close']:.2f}</td>
            <td data-sort="{r['market_cap'] if r['market_cap'] else -1}">{format_number(r['market_cap'])}</td>
            <td data-sort="{r['daily_trading_value']}">{format_number(r['daily_trading_value'])}</td>
            <td data-sort="{r['pct_from_ema30'] if r['pct_from_ema30'] is not None else -9999}">{pct}</td>
            <td>{sector_trend.get(r['sector'], '—')}</td>
            {extra_cols}
        </tr>"""
    return rows


sortable_js = """
<script>
function sortTable(tableId, colIndex, isNumeric) {
    const table = document.getElementById(tableId);
    const rows = Array.from(table.querySelectorAll('tr')).slice(1);
    const asc = table.dataset.sortCol == colIndex ? table.dataset.sortDir !== 'asc' : true;
    rows.sort((a, b) => {
        let x = a.cells[colIndex], y = b.cells[colIndex];
        if (!x || !y) return 0;
        if (isNumeric) {
            let xv = parseFloat(x.dataset.sort ?? x.innerText);
            let yv = parseFloat(y.dataset.sort ?? y.innerText);
            if (isNaN(xv)) xv = -Infinity;
            if (isNaN(yv)) yv = -Infinity;
            return asc ? xv - yv : yv - xv;
        } else {
            return asc ? x.innerText.localeCompare(y.innerText) : y.innerText.localeCompare(x.innerText);
        }
    });
    rows.forEach(r => table.appendChild(r));
    table.dataset.sortCol = colIndex;
    table.dataset.sortDir = asc ? 'asc' : 'desc';
}
</script>
"""


def table_header(table_id, extra_headers=""):
    cols = [
        ("代码", 0, False), ("公司名称", 1, False), ("行业", 2, False),
        ("价格 (RM)", 3, True), ("市值 (RM)", 4, True), ("当日成交额 (RM)", 5, True),
        ("距离EMA30%", 6, True), ("行业趋势", 7, False),
    ]
    th = "".join(f'<th onclick="sortTable(\'{table_id}\',{i},{str(numeric).lower()})">{label} ⇅</th>' for label, i, numeric in cols)
    return f"<tr>{th}{extra_headers}</tr>"


html_content = f"""
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>马股每日趋势筛选</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 30px; background: #f7f7f7; }}
    h1 {{ color: #222; }}
    h2 {{ color: #444; margin-top: 40px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #333; color: white; cursor: pointer; user-select: none; }}
    th:hover {{ background: #555; }}
    tr:nth-child(even) {{ background: #f2f2f2; }}
    .timestamp {{ color: #888; font-size: 14px; }}
</style>
{sortable_js}
</head>
<body>
    <h1>马股每日趋势筛选清单</h1>
    <p class="timestamp">更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

    <div style="background:#f0f0f0; border-left: 6px solid {verdict_color}; padding: 15px 20px; margin: 20px 0; font-size: 16px;">
        <strong>📊 今日大盘宽度：</strong>{market_summary}
    </div>

    <h2>🟢 今日触发信号（Entry Signal）— {len(triggered)} 只</h2>
    <table id="table1">
        {table_header("table1")}
        {build_table_rows(triggered) if triggered else '<tr><td colspan="8">今日无触发信号</td></tr>'}
    </table>

    <h2>🟡 等待突破中（阶段2：回踩支撑）— {len(pending)} 只</h2>
    <table id="table2">
        {table_header("table2")}
        {build_table_rows(pending) if pending else '<tr><td colspan="8">暂无股票处于该阶段</td></tr>'}
    </table>

    <h2>🔵 近期已突破（过去10天内触发过）— {len(recent_breakout_list)} 只</h2>
    <table id="table3">
        {table_header("table3", '<th onclick="sortTable(\'table3\',8,false)">突破日期 ⇅</th><th onclick="sortTable(\'table3\',9,true)">距今 ⇅</th><th onclick="sortTable(\'table3\',10,true)">突破后涨跌% ⇅</th>')}
        {build_table_rows(recent_breakout_list, show_breakout_info=True) if recent_breakout_list else '<tr><td colspan="11">暂无</td></tr>'}
    </table>
</body>
</html>
"""

# ============ 保存网页（带历史记录）============
os.makedirs("history", exist_ok=True)

today_str = datetime.now().strftime('%Y-%m-%d')
dated_filename = f"history/screener_{today_str}.html"

with open(dated_filename, "w", encoding="utf-8") as f:
    f.write(html_content)

with open("screener_output.html", "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"\n✅ 今日网页已生成：{dated_filename}")

# ============ 生成目录页 ============
history_files = sorted(
    [f for f in os.listdir("history") if f.startswith("screener_") and f.endswith(".html")],
    reverse=True
)

index_rows = "".join(
    f'<li><a href="history/{f}">{f.replace("screener_", "").replace(".html", "")}</a></li>'
    for f in history_files
)

index_html = f"""
<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>马股筛选历史记录</title>
<style>
    body {{ font-family: Arial, sans-serif; margin: 30px; }}
    li {{ margin: 8px 0; font-size: 16px; }}
    a {{ text-decoration: none; color: #06c; }}
    a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
    <h1>马股筛选 — 历史记录</h1>
    <p><a href="screener_output.html"><strong>👉 查看今日最新清单</strong></a></p>
    <ul>{index_rows}</ul>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(index_html)

print(f"✅ 历史目录已更新：index.html（共 {len(history_files)} 天记录）")