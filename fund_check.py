#!/usr/bin/env python3
"""
AI基金每日收盘提醒脚本 v2
数据来源：天天基金网 | 推送：Server酱
"""

import os
import re
import json
import urllib.request
import urllib.parse
from datetime import datetime

HOLDINGS = [
    {"code": "004320", "name": "前海开源沪港深乐享", "cost_nav": 6.6307, "shares": 1508.13, "sector": "港股+AI消费", "style": "进攻仓"},
    {"code": "018993", "name": "中欧数字经济A", "cost_nav": 3.8665, "shares": 12931.62, "sector": "AI算力", "style": "主力仓"},
    {"code": "001665", "name": "平安鑫安C", "cost_nav": 2.8534, "shares": 17522.96, "sector": "AI电力", "style": "防守仓"},
]

STOP_LOSS_PCT = -20
STOP_PROFIT_PCT = 60
ALERT_UP_PCT = 3
ALERT_DOWN_PCT = -3

SECTOR_ANALYSIS = {
    "AI算力": {
        "bullish": "AI算力需求持续爆发，全球云商资本支出大幅上调，中期1-2季度逻辑不变。",
        "bearish": "算力板块短期过热回调，但AI产业长期增长逻辑未变，回调即布局窗口。",
        "neutral": "算力板块震荡整理，AI训练推理Token数持续飙升，中期逻辑硬，回调可加仓。",
    },
    "AI电力": {
        "bullish": "AI数据中心电力缺口扩大至55GW，电力是算力上游确定性赛道，短期动能强。",
        "bearish": "电力板块短期回调，与算力跷跷板效应。但AI电力需求中期确定性高，回调是加仓机会。",
        "neutral": "电力板块横盘整理，AI数据中心电力缺口持续扩大，中期逻辑不变，耐心持有。",
    },
    "港股+AI消费": {
        "bullish": "港股回暖+AI消费双轮驱动，沪港深配置优势显现。",
        "bearish": "港股受外围影响回调，但港股估值仍处历史低位，长期配置价值在。",
        "neutral": "港股+AI消费板块震荡，港股估值修复+AI消费渗透是中期逻辑，高位需控制仓位。",
    },
}

def fetch_fund_data(code):
    result = {"code": code}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Referer": "https://fund.eastmoney.com/"}

    url1 = f"https://fundgz.1234567.com.cn/js/{code}.js"
    try:
        req = urllib.request.Request(url1, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
        m = re.match(r'jsonpgz\((.*)\)', raw)
        if m:
            data = json.loads(m.group(1))
            result["nav"] = float(data.get("gsz", 0))
            result["daily_pct"] = float(data.get("gszzl", 0))
            result["nav_date"] = data.get("gztime", "")[:10]
    except Exception as e:
        print(f"  API1失败: {e}")

    url2 = f"https://fundsuggest.eastmoney.com/FundSearch/api/FundSearchAPI.ashx?callback=&amp;m=1&amp;key={code}"
    try:
        req2 = urllib.request.Request(url2, headers=headers)
        with urllib.request.urlopen(req2, timeout=10) as resp:
            raw2 = resp.read().decode("utf-8")
        data2 = json.loads(raw2)
        if data2.get("ErrCode") == 0 and data2.get("Datas"):
            fbi = data2["Datas"][0].get("FundBaseInfo", {})
            if "nav" not in result and fbi.get("DWJZ"):
                result["nav"] = float(fbi["DWJZ"])
            if fbi.get("FSRQ"):
                result["nav_date"] = fbi["FSRQ"][:10]
    except Exception as e:
        print(f"  API2失败: {e}")

    if "week_pct" not in result:
        url3 = f"https://fund.eastmoney.com/{code}.html"
        try:
            req3 = urllib.request.Request(url3, headers=headers)
            with urllib.request.urlopen(req3, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            idx = html.find('近1周</div></th>')
            if idx >= 0:
                snippet = html[idx:idx+3000]
                pcts = re.findall(r'Rdata[^>]*>\s*([+-]?[\d.]+)%\s*</div>', snippet)
                if len(pcts) >= 3:
                    result["week_pct"] = pcts[0]
                    result["month_pct"] = pcts[1]
                    result["quarter_pct"] = pcts[2]
        except Exception as e:
            print(f"  API3失败: {e}")

    if "nav" not in result:
        url4 = f"https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&amp;pageIndex=1&amp;pageSize=1"
        try:
            req4 = urllib.request.Request(url4, headers=headers)
            with urllib.request.urlopen(req4, timeout=10) as resp:
                data4 = json.loads(resp.read().decode("utf-8"))
            if "Data" in data4 and data4["Data"]["LSJZList"]:
                item = data4["Data"]["LSJZList"][0]
                result["nav"] = float(item.get("DWJZ", 0))
                result["nav_date"] = item.get("FSRQ", "")
                if item.get("JZZZL"):
                    try: result["daily_pct"] = float(item["JZZZL"])
                    except: pass
        except Exception as e:
            print(f"  API4失败: {e}")

    return result

def calc_holding(h, nav):
    cost_total = h["cost_nav"] * h["shares"]
    value_total = nav * h["shares"]
    profit = value_total - cost_total
    profit_pct = (nav - h["cost_nav"]) / h["cost_nav"] * 100
    return {"cost_total": cost_total, "value_total": value_total, "profit": profit, "profit_pct": profit_pct}

def get_advice(profit_pct, daily_pct, style):
    alerts = []
    action = "持有"
    reason = ""
    if profit_pct <= STOP_LOSS_PCT:
        alerts.append("🚨 止损预警")
        action = "止损"
        reason = f"持仓亏损已达{profit_pct:.1f}%，突破止损线{STOP_LOSS_PCT}%，果断止损"
    elif profit_pct >= STOP_PROFIT_PCT:
        alerts.append("🎉 止盈预警")
        action = "止盈减仓"
        reason = f"持仓盈利已达{profit_pct:.1f}%，突破止盈线+{STOP_PROFIT_PCT}%，分批减仓落袋（可小程序推送）"
    elif daily_pct >= ALERT_UP_PCT:
        alerts.append("📈 大涨预警")
        action = "持有/考虑减仓1/3"
        reason = f"单日大涨{daily_pct:+.2f}%，短线获利盘可能回吐，{style}可减仓1/3锁利"
    elif daily_pct <= ALERT_DOWN_PCT:
        alerts.append("📉 大跌预警")
        action = "持有/考虑补仓"
        reason = f"单日大跌{daily_pct:+.2f}%，若基本面无变化，{style}可小仓位补仓拉低成本"
    elif profit_pct >= 30:
        action = "持有/分批减仓"
        reason = f"盈利{profit_pct:.1f}%，距止盈线+{STOP_PROFIT_PCT}%还有空间，可每涨5%减仓1/4"
    elif profit_pct >= 10:
        action = "持有"
        reason = f"盈利{profit_pct:.1f}%，{style}运行良好，继续持有让利润奔跑"
    elif profit_pct >= 0:
        action = "持有"
        reason = f"微盈{profit_pct:.1f}%，{style}安全边际充足，无需操作"
    elif profit_pct >= -10:
        action = "持有"
        reason = f"浮亏{profit_pct:.1f}%，距止损线-20%尚远，{style}中期逻辑未变，耐心持有"
    elif profit_pct >= -15:
        action = "持有/密切关注"
        reason = f"亏损{profit_pct:.1f}%，接近止损线，需密切关注"
    else:
        action = "观望/准备止损"
        reason = f"亏损{profit_pct:.1f}%，接近止损线，密切盯盘"
    return action, reason, alerts

def build_report(all_data):
    today = datetime.now().strftime("%m月%d日")
    lines = []
    lines.append(f"【{today}｜三只AI基金收盘提醒】\n")

    lines.append("一、今日盈亏概览")
    lines.append("基金 | 仓位 | 成本 | 净值 | 日涨跌 | 市值 | 盈亏 | 比例 | 操作")
    lines.append("---|---|---|---|---|---|---|---|---")

    total_cost = 0
    total_value = 0
    all_alerts = []

    for d in all_data:
        h = d["holding_cfg"]
        nav = d.get("nav")
        daily_pct = d.get("daily_pct", 0)
        pi = d.get("profit_info")
        if nav is None or pi is None:
            lines.append(f"{h['code']} {h['name']} | {h['style']} | {h['cost_nav']} | 获取失败 | - | - | - | - | -")
            continue
        action, reason, alerts = get_advice(pi["profit_pct"], daily_pct, h["style"])
        all_alerts.extend(alerts)
        ds = f"{daily_pct:+.2f}%" if isinstance(daily_pct, (int, float)) else str(daily_pct)
        tag = "⚠️" if alerts else ""
        lines.append(f"{h['code']} {h['name']} | {h['style']} | {h['cost_nav']} | {nav} | {ds}{tag} | {pi['value_total']:.0f} | {pi['profit']:+.0f} | {pi['profit_pct']:+.2f}% | {action}")
        total_cost += pi["cost_total"]
        total_value += pi["value_total"]

    tp = total_value - total_cost
    tpp = tp / total_cost * 100 if total_cost else 0
    lines.append(f"\n总投入：{total_cost:,.0f}元 | 市值：{total_value:,.0f}元 | 盈亏：{tp:+,.0f}元({tpp:+.2f}%)\n")

    if all_alerts:
        lines.append("⚠️ 预警提示")
        for a in all_alerts:
            lines.append(f"  {a}")
        lines.append("")

    lines.append("二、逐只详细解读")
    for d in all_data:
        h = d["holding_cfg"]
        nav = d.get("nav")
        daily_pct = d.get("daily_pct", 0)
        pi = d.get("profit_info")
        if not nav or not pi:
            continue
        action, reason, alerts = get_advice(pi["profit_pct"], daily_pct, h["style"])
        ds = f"{daily_pct:+.2f}%" if isinstance(daily_pct, (int, float)) else str(daily_pct)
        w = d.get("week_pct", "N/A")
        m = d.get("month_pct", "N/A")
        q = d.get("quarter_pct", "N/A")
        lines.append(f"\n{h['code']} {h['name']}（{h['style']}｜{h['sector']}）")
        lines.append(f"  今日：{ds} | 近一周：{w}% | 近一月：{m}% | 近三月：{q}%")
        lines.append(f"  持仓：{h['shares']:.2f}份 | 成本净值：{h['cost_nav']} | 当前净值：{nav}")
        lines.append(f"  盈亏：{pi['profit']:+,.2f}元（{pi['profit_pct']:+.2f}%）")
        lines.append(f"  操作：{action}")
        lines.append(f"  理由：{reason}")

    lines.append("\n三、板块与前景分析")
    for d in all_data:
        h = d["holding_cfg"]
        daily_pct = d.get("daily_pct", 0)
        if isinstance(daily_pct, str):
            try: daily_pct = float(daily_pct)
            except: daily_pct = 0
        sector = h["sector"]
        analysis = SECTOR_ANALYSIS.get(sector, {})
        if daily_pct >= 1:
            outlook = analysis.get("bullish", "板块走势偏强。")
        elif daily_pct <= -1:
            outlook = analysis.get("bearish", "板块短期承压。")
        else:
            outlook = analysis.get("neutral", "板块震荡整理。")
        lines.append(f"  {sector}（影响 {h['name']}）：{outlook}")
    lines.append("  整体判断：AI产业核心矛盾从算力转向电力。算力是矛，电力是盾，两者轮动是常态。主力仓（算力）+ 防守仓（电力）+ 进攻仓（港股AI），攻守兼备。AI仍是2026年最强主线。")

    lines.append("\n四、买卖时机与价位参考")
    for d in all_data:
        h = d["holding_cfg"]
        nav = d.get("nav")
        pi = d.get("profit_info")
        if not nav or not pi:
            continue
        cost = h["cost_nav"]
        buy_low = round(cost * 0.90, 4)
        buy_high = round(cost * 0.95, 4)
        sell = round(cost * (1 + STOP_PROFIT_PCT / 100), 4)
        stop = round(cost * (1 + STOP_LOSS_PCT / 100), 4)
        lines.append(f"  {h['code']} {h['name']}（{h['style']}）")
        lines.append(f"    成本价：{cost} | 当前净值：{nav}")
        if pi["profit_pct"] < 0:
            lines.append(f"    加仓区间：净值跌至 {buy_low} ~ {buy_high} 分批补仓")
        else:
            lines.append(f"    减仓区间：净值涨至 {sell} 附近分批减仓")
        lines.append(f"    止损价：{stop} | 止盈价：{sell}")
        lines.append(f"    分批策略：每次加减仓不超过1/3仓位，间隔2-3个交易日")

    lines.append("\n五、明日策略")
    for d in all_data:
        h = d["holding_cfg"]
        nav = d.get("nav")
        pi = d.get("profit_info")
        dp = d.get("daily_pct", 0)
        if not pi:
            continue
        if isinstance(dp, str):
            try: dp = float(dp)
            except: dp = 0
        pct = pi["profit_pct"]
        cost = h["cost_nav"]
        if pct <= STOP_LOSS_PCT:
            lines.append(f"  {h['name']}：🚨 触及止损线！明日果断止损离场")
        elif pct >= STOP_PROFIT_PCT:
            lines.append(f"  {h['name']}：🎉 触及止盈线！明日分批减仓，先出1/3")
        elif dp >= ALERT_UP_PCT:
            lines.append(f"  {h['name']}：📈 今日大涨，明日若冲高回落减仓1/3锁利")
        elif dp <= ALERT_DOWN_PCT:
            lines.append(f"  {h['name']}：📉 今日大跌，明日若继续下跌可补仓1万拉低成本")
        elif pct < -10:
            lines.append(f"  {h['name']}：亏损超10%，密切关注，净值跌至{round(cost*0.8,4)}止损线果断离场")
        elif pct < 0:
            lines.append(f"  {h['name']}：小幅浮亏，继续持有。净值跌至{round(cost*0.95,4)}以下可补仓1万")
        elif pct < 20:
            lines.append(f"  {h['name']}：正常盈利，继续持有让利润奔跑")
        elif pct < 40:
            lines.append(f"  {h['name']}：盈利丰厚，可考虑每涨5%减仓1/4逐步落袋")
        else:
            lines.append(f"  {h['name']}：接近止盈区，制定分批减仓计划")

    lines.append(f"\n止损线 {STOP_LOSS_PCT}% | 止盈线 +{STOP_PROFIT_PCT}% | 大涨预警 ≥+{ALERT_UP_PCT}% | 大跌预警 ≤{ALERT_DOWN_PCT}%")
    lines.append(f"数据来源：天天基金网 | 推送：方糖Server酱 | 每交易日22:00自动推送")

    return "\n".join(lines)

def push_to_serverchan(title, content, sckey):
    url = f"https://sctapi.ftqq.com/{sckey}.send"
    if len(content) > 25000:
        content = content[:25000] + "\n...(内容过长已截断)"
    data = urllib.parse.urlencode({"title": title[:100], "desp": content}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("code") == 0, result
    except Exception as e:
        return False, str(e)

def main():
    print(f"[{datetime.now()}] 开始抓取基金数据...")
    all_data = []
    for h in HOLDINGS:
        print(f"  抓取 {h['code']} {h['name']} ...")
        fd = fetch_fund_data(h["code"])
        fd["holding_cfg"] = h
        nav = fd.get("nav")
        if nav:
            fd["profit_info"] = calc_holding(h, nav)
            print(f"    净值={nav} 日涨跌={fd.get('daily_pct','N/A')}% 盈亏={fd['profit_info']['profit']:+.2f}")
        else:
            fd["profit_info"] = None
            print(f"    ❌ 数据获取失败")
        all_data.append(fd)

    report = build_report(all_data)
    today = datetime.now().strftime("%m月%d日")
    title = f"【{today}｜三只AI基金收盘提醒】"

    print("\n" + "=" * 60)
    print(report)
    print("=" * 60)

    sckey = os.environ.get("SERVERCHAN_KEY", "")
    if sckey:
        print(f"\n推送到 Server酱...")
        ok, result = push_to_serverchan(title, report, sckey)
        if ok:
            print("  ✅ 推送成功！")
        else:
            print(f"  ❌ 推送失败：{result}")
    else:
        print("\n⚠️ 未配置 SERVERCHAN_KEY，跳过推送")

    print(f"\n[{datetime.now()}] 完成。")

if __name__ == "__main__":
    main()
