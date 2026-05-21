#!/usr/bin/env python3
"""
AI基金每日收盘提醒脚本 —— 你的专属版
数据：天天基金网 | 推送：Server酱 | 清爽易读
"""

import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime

# ====================== 【你的真实持仓 100% 精准】======================
HOLDINGS = [
    {
        "code": "004320",
        "name": "前海开源沪港深乐享",
        "cost_nav": 6.6307,
        "shares": 1508.13,
    },
    {
        "code": "018993",
        "name": "中欧数字经济A",
        "cost_nav": 3.9408,
        "shares": 12931.62,
    },
    {
        "code": "001665",
        "name": "平安鑫安C",
        "cost_nav": 2.8229,
        "shares": 17522.96,
    },
]

TOTAL_INVEST = 160000  # 你的真实总本金

# ====================== 抓取基金官方净值 ======================
def fetch_fund_data(code):
    result = {"code": code}
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        url = f"https://fundgz.1234567.com.cn/js/{code}.js"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            raw = resp.read().decode("utf-8")
        m = re.match(r'jsonpgz\((.*)\)', raw)
        if m:
            data = json.loads(m.group(1))
            result["nav"] = float(data.get("gsz", 0))
            result["daily_pct"] = float(data.get("gszzl", 0))
    except:
        pass
    return result

# ====================== 计算盈亏 ======================
def calc(h, nav):
    cost = h["cost_nav"] * h["shares"]
    now = nav * h["shares"]
    profit = now - cost
    profit_pct = (nav - h["cost_nav"]) / h["cost_nav"] * 100
    daily_pnl = now * h["daily_pct"] / 100
    return {
        "cost": cost,
        "now": now,
        "profit": profit,
        "profit_pct": profit_pct,
        "daily_pnl": daily_pnl
    }

# ====================== 清爽版报告（易读！）======================
def build_report(datas):
    today = datetime.now().strftime("%m-%d")
    lines = []

    lines.append(f"📅 {today} 基金收盘简报\n")

    total_now = 0
    total_day = 0

    for d in datas:
        h = d["hold"]
        nav = d.get("nav")
        dp = d.get("daily_pct", 0)
        c = d["calc"]
        total_now += c["now"]
        total_day += c["daily_pnl"]

        lines.append(f"【{h['name']}】")
        lines.append(f"  今日：{dp:+.2f}% | 盈亏：{c['daily_pnl']:+.0f} 元")
        lines.append(f"  持仓：{c['now']:.0f} 元 | 总收益：{c['profit']:+.0f} 元 ({c['profit_pct']:+.1f}%)")
        lines.append("")

    total_profit = total_now - TOTAL_INVEST
    total_pct = total_profit / TOTAL_INVEST * 100

    lines.append("========================")
    lines.append(f"🏦 总投入：{TOTAL_INVEST} 元")
    lines.append(f"💰 总市值：{total_now:.0f} 元")
    lines.append(f"📊 今日总盈亏：{total_day:+.0f} 元")
    lines.append(f"✅ 累计总盈亏：{total_profit:+.0f} 元 ({total_pct:+.1f}%)")
    lines.append("========================")

    lines.append("\n🎯 操作建议：")
    for d in datas:
        h = d["hold"]
        pp = d["calc"]["profit_pct"]
        dp = d.get("daily_pct", 0)

        if pp >= 15:
            adv = "盈利丰厚 → 可分批减仓落袋"
        elif pp >= 5:
            adv = "稳健盈利 → 继续持有"
        elif pp >= 0:
            adv = "微盈 → 耐心持有"
        elif pp >= -5:
            adv = "小幅浮亏 → 正常波动，持有"
        else:
            adv = "浮亏偏大 → 观望为主，不加仓"

        lines.append(f"• {h['name']}：{adv}")

    return "\n".join(lines)

# ====================== 推送 ======================
def push(title, content, key):
    url = f"https://sctapi.ftqq.com/{key}.send"
    data = urllib.parse.urlencode({"title": title, "desp": content}).encode()
    try:
        req = urllib.request.Request(url, data=data)
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read()).get("code") == 0
    except:
        return False

# ====================== 主程序 ======================
def main():
    datas = []
    for h in HOLDINGS:
        fd = fetch_fund_data(h["code"])
        fd["hold"] = h
        if fd.get("nav"):
            fd["calc"] = calc(h, fd["nav"])
        datas.append(fd)

    report = build_report(datas)
    print(report)

    key = os.environ.get("SERVERCHAN_KEY")
    if key:
        push(f"基金收盘简报 {datetime.now().strftime('%m-%d')}", report, key)

if __name__ == "__main__":
    main()
