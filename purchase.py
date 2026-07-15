# -*- coding: utf-8 -*-
"""
彩票购买记录与开奖对比模块
功能: 保存购买号码、记录购买期数、开奖后对比中奖、计算奖金、生成改进建议
"""

import json
import os
import time
import uuid
from datetime import datetime, timedelta
from analyzer import LOTTERY_CONFIG

# 开奖时间表 (weekday: 0=周一 ... 6=周日)
SSQ_DRAW_WEEKDAYS = [1, 3, 6]   # 周二、周四、周日
DLT_DRAW_WEEKDAYS = [0, 2, 4]   # 周一、周三、周五
SSQ_DRAW_TIME = (21, 15)        # 21:15
DLT_DRAW_TIME = (20, 30)        # 20:30


def get_draw_schedule(lottery_type):
    """获取彩种开奖日和开奖时间"""
    if lottery_type == "ssq":
        return {
            "days": "周二、周四、周日",
            "time": "21:15",
            "weekdays": SSQ_DRAW_WEEKDAYS,
        }
    else:
        return {
            "days": "周一、周三、周五",
            "time": "20:30",
            "weekdays": DLT_DRAW_WEEKDAYS,
        }


def get_next_draw_time(lottery_type):
    """计算下一次开奖时间"""
    schedule = get_draw_schedule(lottery_type)
    now = datetime.now()
    hour, minute = schedule["time"].split(":")
    hour, minute = int(hour), int(minute)

    for offset in range(8):
        check_date = now + timedelta(days=offset)
        if check_date.weekday() in schedule["weekdays"]:
            draw_dt = check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if now < draw_dt:
                return draw_dt
    return None


def check_draw_status(issue, lottery_type):
    """检查某期是否已开奖
    返回: {"drawn": bool, "draw_data": dict/None, "message": str}
    """
    from scraper import get_ssq_data, get_dlt_data

    if lottery_type == "ssq":
        data = get_ssq_data(limit=500)
    else:
        data = get_dlt_data(limit=500)

    if not data:
        return {"drawn": False, "draw_data": None, "message": "数据加载中，请稍后重试"}

    # 在缓存数据中查找该期
    draw = next((d for d in data if str(d["issue"]) == str(issue)), None)

    if draw:
        if lottery_type == "ssq":
            return {
                "drawn": True,
                "draw_data": {"issue": draw["issue"], "red": draw["red"], "blue": [draw["blue"]]},
                "message": "已开奖",
            }
        else:
            return {
                "drawn": True,
                "draw_data": {"issue": draw["issue"], "red": draw["front"], "blue": draw["back"]},
                "message": "已开奖",
            }

    # 未在数据中找到
    latest_issue = data[0]["issue"]
    if int(str(issue)) > int(str(latest_issue)):
        schedule = get_draw_schedule(lottery_type)
        next_draw = get_next_draw_time(lottery_type)
        next_str = next_draw.strftime("%m月%d日 %H:%M") if next_draw else "未知"
        return {
            "drawn": False,
            "draw_data": None,
            "message": f"未开奖（{schedule['days']} {schedule['time']}），下次开奖: {next_str}",
        }

    return {
        "drawn": False,
        "draw_data": None,
        "message": "开奖数据未更新，请点击「刷新数据」",
    }

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PURCHASE_FILE = os.path.join(BASE_DIR, "purchases.json")

# 中奖规则 (固定奖 + 浮动奖标识)
SSQ_PRIZES = {
    (6, 1): {"name": "一等奖", "amount_type": "浮动", "estimate": 5000000, "fixed": False},
    (6, 0): {"name": "二等奖", "amount_type": "浮动", "estimate": 200000, "fixed": False},
    (5, 1): {"name": "三等奖", "amount_type": "固定", "amount": 3000, "fixed": True},
    (5, 0): {"name": "四等奖", "amount_type": "固定", "amount": 200, "fixed": True},
    (4, 1): {"name": "四等奖", "amount_type": "固定", "amount": 200, "fixed": True},
    (4, 0): {"name": "五等奖", "amount_type": "固定", "amount": 10, "fixed": True},
    (3, 1): {"name": "五等奖", "amount_type": "固定", "amount": 10, "fixed": True},
    (2, 1): {"name": "六等奖", "amount_type": "固定", "amount": 5, "fixed": True},
    (1, 1): {"name": "六等奖", "amount_type": "固定", "amount": 5, "fixed": True},
    (0, 1): {"name": "六等奖", "amount_type": "固定", "amount": 5, "fixed": True},
}

DLT_PRIZES = {
    (5, 2): {"name": "一等奖", "amount_type": "浮动", "estimate": 10000000, "fixed": False},
    (5, 1): {"name": "二等奖", "amount_type": "浮动", "estimate": 500000, "fixed": False},
    (5, 0): {"name": "三等奖", "amount_type": "固定", "amount": 10000, "fixed": True},
    (4, 2): {"name": "四等奖", "amount_type": "固定", "amount": 3000, "fixed": True},
    (4, 1): {"name": "五等奖", "amount_type": "固定", "amount": 300, "fixed": True},
    (3, 2): {"name": "六等奖", "amount_type": "固定", "amount": 200, "fixed": True},
    (4, 0): {"name": "七等奖", "amount_type": "固定", "amount": 100, "fixed": True},
    (3, 1): {"name": "八等奖", "amount_type": "固定", "amount": 15, "fixed": True},
    (2, 2): {"name": "八等奖", "amount_type": "固定", "amount": 15, "fixed": True},
    (3, 0): {"name": "九等奖", "amount_type": "固定", "amount": 5, "fixed": True},
    (2, 1): {"name": "九等奖", "amount_type": "固定", "amount": 5, "fixed": True},
    (1, 2): {"name": "九等奖", "amount_type": "固定", "amount": 5, "fixed": True},
    (0, 2): {"name": "九等奖", "amount_type": "固定", "amount": 5, "fixed": True},
}


def load_purchases():
    """加载所有购买记录"""
    if not os.path.exists(PURCHASE_FILE):
        return []
    try:
        with open(PURCHASE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_purchases(purchases):
    """保存购买记录"""
    with open(PURCHASE_FILE, "w", encoding="utf-8") as f:
        json.dump(purchases, f, ensure_ascii=False, indent=2)


def add_purchase(lottery_type, issue, red, blue, strategy="", source="system", cost=2.0, note=""):
    """
    添加一条购买记录
    lottery_type: ssq / dlt
    issue: 购买期号
    red: 红球/前区号码列表
    blue: 蓝球/后区号码列表 (SSQ是整数, DLT是列表)
    """
    purchases = load_purchases()
    cfg = LOTTERY_CONFIG[lottery_type]

    # 统一处理blue格式
    if lottery_type == "ssq":
        blue_norm = [int(blue)] if not isinstance(blue, (list, tuple)) else [int(b) for b in blue]
    else:
        blue_norm = [int(b) for b in blue]

    record = {
        "id": str(uuid.uuid4())[:12],
        "lottery_type": lottery_type,
        "lottery_name": cfg["name"],
        "issue": str(issue),
        "red": sorted([int(r) for r in red]),
        "blue": blue_norm,
        "strategy": strategy,
        "source": source,
        "cost": float(cost),
        "note": note,
        "status": "pending",  # pending / checked
        "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "check_time": None,
        "win": None,
        "match": None,
        "prize": None,
    }
    purchases.append(record)
    save_purchases(purchases)
    return record


def add_purchase_batch(records):
    """批量添加购买记录
    records: [{lottery_type, issue, red, blue, strategy, source, cost, note}, ...]
    """
    results = []
    for rec in records:
        results.append(add_purchase(**rec))
    return results


def delete_purchase(purchase_id):
    """删除购买记录"""
    purchases = load_purchases()
    purchases = [p for p in purchases if p["id"] != purchase_id]
    save_purchases(purchases)
    return True


def update_purchase_issue(purchase_id, new_issue):
    """修改购买记录的期号，并重置对比状态。

    期号变更后，旧的对比结果（中奖/未中奖）已失效，统一重置为 pending，
    待用户重新「开奖对比」时按新期号判断。
    """
    purchases = load_purchases()
    for p in purchases:
        if p["id"] == purchase_id:
            p["issue"] = str(new_issue)
            # 重置对比相关字段
            p["status"] = "pending"
            p["check_time"] = None
            p["win"] = None
            p["match"] = None
            p["prize"] = None
            p["drawn_red"] = None
            p["drawn_blue"] = None
            save_purchases(purchases)
            return p
    return None


def get_purchases(lottery_type=None, status=None, issue=None):
    """获取购买记录,支持筛选"""
    purchases = load_purchases()
    if lottery_type:
        purchases = [p for p in purchases if p["lottery_type"] == lottery_type]
    if status:
        purchases = [p for p in purchases if p["status"] == status]
    if issue:
        purchases = [p for p in purchases if p["issue"] == str(issue)]
    # 按时间倒序
    purchases.sort(key=lambda x: x["create_time"], reverse=True)
    return purchases


def check_purchase(purchase_id, draw_data=None):
    """
    检查单条购买记录是否中奖
    draw_data: {issue, red, blue} 如果未传入, 自动判断是否已开奖
    返回值:
      - 未开奖: {"id":..., "not_drawn": True, "message": "...", "status": "pending", ...}
      - 已开奖: purchase记录 (含 not_drawn=False, match, prize等)
      - 不存在: None
    """
    purchases = load_purchases()
    purchase = next((p for p in purchases if p["id"] == purchase_id), None)
    if not purchase:
        return None

    lottery_type = purchase["lottery_type"]
    issue = purchase["issue"]

    # 如果未提供开奖数据，自动判断是否已开奖
    if draw_data is None:
        status = check_draw_status(issue, lottery_type)
        if not status["drawn"]:
            # 未开奖，不修改记录，返回特殊结果
            result = dict(purchase)
            result["not_drawn"] = True
            result["draw_message"] = status["message"]
            return result
        draw_data = status["draw_data"]

    # 已开奖，计算命中
    my_red = set(purchase["red"])
    my_blue = set(purchase["blue"])
    win_red = set(draw_data["red"])
    win_blue = set(draw_data["blue"])

    red_match = len(my_red & win_red)
    blue_match = len(my_blue & win_blue)

    if lottery_type == "ssq":
        prize_info = SSQ_PRIZES.get((red_match, blue_match), {"name": "未中奖", "amount": 0, "fixed": True, "amount_type": "固定"})
    else:
        prize_info = DLT_PRIZES.get((red_match, blue_match), {"name": "未中奖", "amount": 0, "fixed": True, "amount_type": "固定"})

    amount = prize_info.get("amount", 0) if prize_info.get("fixed") else prize_info.get("estimate", 0)
    is_win = prize_info["name"] != "未中奖"

    purchase["status"] = "checked"
    purchase["check_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    purchase["win"] = is_win
    purchase["match"] = {"red": red_match, "blue": blue_match}
    purchase["prize"] = {
        "name": prize_info["name"],
        "amount": amount,
        "amount_type": prize_info["amount_type"],
        "fixed": prize_info["fixed"],
        "estimate": prize_info.get("estimate", amount),
    }
    purchase["drawn_red"] = sorted(list(win_red))
    purchase["drawn_blue"] = sorted(list(win_blue))

    save_purchases(purchases)

    result = dict(purchase)
    result["not_drawn"] = False
    return result


def check_all_purchases(lottery_type=None, issue=None):
    """批量检查所有待开奖记录
    返回: (results, drawn_count, not_drawn_count)
    """
    purchases = load_purchases()
    pending = [p for p in purchases if p["status"] == "pending"]
    if lottery_type:
        pending = [p for p in pending if p["lottery_type"] == lottery_type]
    if issue:
        pending = [p for p in pending if p["issue"] == str(issue)]

    results = []
    drawn_count = 0
    not_drawn_count = 0
    for p in pending:
        result = check_purchase(p["id"])
        if result:
            if result.get("not_drawn"):
                not_drawn_count += 1
            else:
                drawn_count += 1
            results.append(result)
    return results, drawn_count, not_drawn_count


def get_win_summary():
    """获取中奖统计汇总"""
    purchases = load_purchases()
    total_cost = sum(p["cost"] for p in purchases)
    total_win = sum(p["prize"]["amount"] for p in purchases if p.get("prize"))
    win_count = sum(1 for p in purchases if p.get("win"))
    checked_count = sum(1 for p in purchases if p["status"] == "checked")
    pending_count = sum(1 for p in purchases if p["status"] == "pending")
    return {
        "total_cost": round(total_cost, 2),
        "total_win": round(total_win, 2),
        "profit": round(total_win - total_cost, 2),
        "total_count": len(purchases),
        "checked_count": checked_count,
        "pending_count": pending_count,
        "win_count": win_count,
    }


def generate_improvement_suggestions(purchase_id=None, lottery_type=None, periods=50):
    """
    根据历史购买记录和开奖结果,生成改进建议
    可以针对单条记录、单个彩种或全部记录
    """
    from scraper import get_ssq_data, get_dlt_data
    from analyzer import full_analysis

    purchases = load_purchases()
    if purchase_id:
        target = [p for p in purchases if p["id"] == purchase_id]
    elif lottery_type:
        target = [p for p in purchases if p["lottery_type"] == lottery_type]
    else:
        target = purchases

    if not target:
        return {"suggestions": ["暂无购买记录,无法生成建议。建议先记录几注购买号码并等待开奖。"], "stats": {}}

    # 只分析已开奖记录
    checked = [p for p in target if p["status"] == "checked"]
    wins = [p for p in checked if p.get("win")]
    losses = [p for p in checked if not p.get("win")]

    suggestions = []
    stats = {
        "total_checked": len(checked),
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": round(len(wins) / len(checked) * 100, 1) if checked else 0,
        "total_cost": round(sum(p["cost"] for p in checked), 2),
        "total_win": round(sum(p["prize"]["amount"] for p in checked if p.get("prize")), 2),
    }

    # 建议1: 总体胜率与随机期望对比
    if checked:
        expected_rate = 5.6 if target[0]["lottery_type"] == "ssq" else 5.2
        if stats["win_rate"] < expected_rate:
            suggestions.append(f"当前胜率{stats['win_rate']}%低于理论期望({expected_rate}%)。彩票长期期望为负,建议减少投入或改为小额娱乐。")
        else:
            suggestions.append(f"当前胜率{stats['win_rate']}%高于理论期望,但样本量可能不足,需持续观察。")

    # 建议2: 策略效果分析
    if checked:
        strat_perf = {}
        for p in checked:
            s = p.get("strategy", "unknown")
            if s not in strat_perf:
                strat_perf[s] = {"count": 0, "win": 0, "cost": 0, "win_amount": 0}
            strat_perf[s]["count"] += 1
            strat_perf[s]["cost"] += p["cost"]
            if p.get("win"):
                strat_perf[s]["win"] += 1
                strat_perf[s]["win_amount"] += p["prize"]["amount"]

        # 找出表现最好和最差的策略
        if strat_perf:
            best = max(strat_perf.items(), key=lambda x: x[1]["win"])
            worst = min(strat_perf.items(), key=lambda x: x[1]["win"])
            suggestions.append(f"策略效果: 「{best[0]}」中奖次数最多({best[1]['win']}次), 「{worst[0]}」最少。可暂时多尝试「{best[0]}」。")

    # 建议3: 号码特征分析 (针对未中奖号码)
    if losses:
        # 统计未中奖号码的平均和值、跨度、奇偶比
        sums = [sum(p["red"]) for p in losses]
        spans = [max(p["red"]) - min(p["red"]) for p in losses]
        odd_ratios = [sum(1 for n in p["red"] if n % 2 == 1) / len(p["red"]) for p in losses]

        avg_sum = sum(sums) / len(sums)
        avg_span = sum(spans) / len(spans)
        avg_odd = sum(odd_ratios) / len(odd_ratios)

        suggestions.append(f"未中奖号码特征: 平均和值{avg_sum:.1f}, 平均跨度{avg_span:.1f}, 平均奇偶比{avg_odd:.1f}。可适当向历史均值靠拢。")

    # 建议4: 冷热号偏离分析
    if checked:
        lt = target[0]["lottery_type"]
        data = get_ssq_data(limit=periods * 3) if lt == "ssq" else get_dlt_data(limit=periods * 3)
        analysis = full_analysis(data, lt, periods)
        hot_set = set(analysis["hot_cold"]["hot"])
        cold_set = set(analysis["hot_cold"]["cold"])

        hot_used = 0
        cold_used = 0
        total_red = 0
        for p in checked:
            total_red += len(p["red"])
            hot_used += len(set(p["red"]) & hot_set)
            cold_used += len(set(p["red"]) & cold_set)

        if total_red > 0:
            hot_pct = hot_used / total_red * 100
            cold_pct = cold_used / total_red * 100
            if hot_pct > 50:
                suggestions.append(f"近期选号中热号占比{hot_pct:.1f}%偏高。热号有回调风险,建议下一期适当增加温冷号比例。")
            elif cold_pct > 40:
                suggestions.append(f"近期选号中冷号占比{cold_pct:.1f}%偏高。冷号回补有滞后性,不要过度追冷。")
            else:
                suggestions.append(f"冷热号比例较为均衡(热{hot_pct:.1f}% 冷{cold_pct:.1f}%),可保持当前节奏。")

    # 建议5: 投入产出比
    if checked:
        profit = stats["total_win"] - stats["total_cost"]
        if profit < 0:
            suggestions.append(f"当前累计亏损{abs(profit):.2f}元。彩票不是投资,建议设定月度预算,单次投入不超过10-20元。")
        else:
            suggestions.append(f"当前累计盈利{profit:.2f}元。建议见好就收,不要把盈利重新全部投入。")

    # 建议6: 蓝球/后区分析
    if checked:
        lt = target[0]["lottery_type"]
        blue_misses = []
        for p in losses:
            my_blue = set(p["blue"])
            if lt == "ssq" and p.get("drawn_blue"):
                if len(my_blue & set(p["drawn_blue"])) == 0:
                    blue_misses.append(p)
            elif lt == "dlt" and p.get("drawn_blue"):
                if len(my_blue & set(p["drawn_blue"])) == 0:
                    blue_misses.append(p)

        if blue_misses:
            suggestions.append(f"有{len(blue_misses)}注未中蓝球/后区。小奖依赖蓝球,可适当关注遗漏较大的蓝球号码。")

    # 建议7: 连号与重号分析
    if losses:
        consec_counts = []
        repeat_counts = []
        prev_red = None
        for p in losses:
            r = sorted(p["red"])
            consec = sum(1 for i in range(len(r) - 1) if r[i + 1] - r[i] == 1)
            consec_counts.append(consec)
            if prev_red:
                repeat = len(set(r) & set(prev_red))
                repeat_counts.append(repeat)
            prev_red = r

        avg_consec = sum(consec_counts) / len(consec_counts)
        if avg_consec > 1.5:
            suggestions.append(f"未中奖号码平均连号数{avg_consec:.1f}偏高。历史中奖号码连号通常较少,建议控制连号数量。")

    # 建议8+: 针对待开奖记录的即时改进建议 (无开奖数据时也能用)
    if target:
        from collections import Counter
        all_reds = []
        all_blues = []
        for p in target:
            all_reds.extend(p["red"])
            all_blues.extend(p["blue"])

        # 红球重复度分析
        red_counter = Counter(all_reds)
        overused = [n for n, c in red_counter.items() if c >= 3]
        if overused:
            top_str = ", ".join([f"{n}号({red_counter[n]}次)" for n in overused])
            suggestions.append(f"本次购买中红球过度集中: {top_str}。号码集中会降低覆盖率,建议分散选号。")

        # 蓝球/后区重复度分析
        blue_counter = Counter(all_blues)
        top_blue = blue_counter.most_common(1)
        if top_blue and top_blue[0][1] >= 3:
            suggestions.append(f"蓝球/后区过度集中: {top_blue[0][0]}号买了{top_blue[0][1]}次。后区小奖依赖度高,建议分散配置。")

        # 和值分布
        sums = [sum(p["red"]) for p in target]
        if sums:
            avg_sum = sum(sums) / len(sums)
            min_sum = min(sums)
            max_sum = max(sums)
            lt = target[0]["lottery_type"]
            data = get_ssq_data(limit=periods * 3) if lt == "ssq" else get_dlt_data(limit=periods * 3)
            analysis = full_analysis(data, lt, periods)
            hist_avg = analysis["sum"]["avg"]
            hist_min = analysis["sum"]["min"]
            hist_max = analysis["sum"]["max"]
            if max_sum > hist_max or min_sum < hist_min:
                suggestions.append(f"本次和值范围[{min_sum}-{max_sum}]超出历史常见范围[{hist_min}-{hist_max}]。建议向历史均值{hist_avg}靠拢。")
            elif abs(avg_sum - hist_avg) > 15:
                suggestions.append(f"本次平均和值{avg_sum:.1f}偏离历史均值{hist_avg:.1f}。建议调整号码分布。")

    if not suggestions:
        suggestions.append("记录数据不足,建议多记录几注并等待开奖后再来查看改进建议。")

    return {"suggestions": suggestions, "stats": stats}


if __name__ == "__main__":
    # 简单测试
    add_purchase("ssq", "26078", [1, 3, 5, 10, 15, 20], [7], strategy="balanced", source="test")
    print("购买记录:", get_purchases())
