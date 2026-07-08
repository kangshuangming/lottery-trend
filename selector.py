# -*- coding: utf-8 -*-
"""
智能选号引擎
基于走势分析结果，多策略组合选号
策略: 热号追势 / 冷号回补 / 遗漏回补 / 均衡组合 / 随机均衡
"""

import random
from analyzer import full_analysis, LOTTERY_CONFIG


def select_red_numbers(data, lottery_type, analysis, strategy="balanced", count=None):
    """根据策略选择红球号码"""
    cfg = LOTTERY_CONFIG[lottery_type]
    if count is None:
        count = cfg["red_count"] if "red_count" in cfg else cfg["front_count"]
    red_max = cfg["red_max"]
    freq = analysis["frequency"]["red"]
    missing = analysis["missing"]["red"]
    hot_cold = analysis["hot_cold"]

    # 号码评分 (0-100)
    scores = {}
    for i in range(1, red_max + 1):
        f_item = next((x for x in freq if x["num"] == i), {"count": 0, "pct": 0})
        m_item = next((x for x in missing if x["num"] == i), {"missing": 0, "avg_gap": 0, "ratio": 0})

        freq_score = f_item["count"]  # 频率越高分越高
        miss_score = m_item["missing"]  # 遗漏越大回补倾向越高
        ratio = m_item["ratio"]  # 遗漏/均值比

        scores[i] = {
            "freq": freq_score,
            "missing": miss_score,
            "ratio": ratio,
            "is_hot": i in hot_cold["hot"],
            "is_cold": i in hot_cold["cold"],
        }

    selected = set()

    if strategy == "hot":
        # 热号追势: 优先选高频号码
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["freq"], reverse=True)
        for num, _ in sorted_nums:
            selected.add(num)
            if len(selected) >= count:
                break

    elif strategy == "cold":
        # 冷号回补: 优先选遗漏比高的号码
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["ratio"], reverse=True)
        for num, _ in sorted_nums:
            selected.add(num)
            if len(selected) >= count:
                break

    elif strategy == "missing":
        # 遗漏回补: 优先选遗漏期数最大的号码
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["missing"], reverse=True)
        for num, _ in sorted_nums:
            selected.add(num)
            if len(selected) >= count:
                break

    elif strategy == "balanced":
        # 均衡组合: 2热+2温+2冷 (或按比例)
        hot = [n for n in hot_cold["hot"] if n not in selected]
        warm = [n for n in hot_cold["warm"] if n not in selected]
        cold = [n for n in hot_cold["cold"] if n not in selected]

        random.shuffle(hot)
        random.shuffle(warm)
        random.shuffle(cold)

        # 按比例分配
        hot_need = max(1, count // 3)
        cold_need = max(1, count // 3)
        warm_need = count - hot_need - cold_need

        for n in hot[:hot_need]:
            selected.add(n)
        for n in warm[:warm_need]:
            selected.add(n)
        for n in cold[:cold_need]:
            selected.add(n)

        # 补齐
        all_remaining = [n for n in range(1, red_max + 1) if n not in selected]
        random.shuffle(all_remaining)
        for n in all_remaining:
            if len(selected) >= count:
                break
            selected.add(n)

    elif strategy == "smart":
        # 智能评分: 综合频率 + 遗漏比 + 随机扰动
        import math
        smart_scores = {}
        for num, info in scores.items():
            # 频率得分 (归一化)
            max_freq = max(s["freq"] for s in scores.values()) or 1
            freq_s = info["freq"] / max_freq * 40
            # 遗漏比得分 (归一化, 超过1.5倍开始加分)
            ratio_s = min(info["ratio"] / 2, 1) * 30
            # 随机扰动
            rand_s = random.random() * 30
            smart_scores[num] = freq_s + ratio_s + rand_s

        sorted_nums = sorted(smart_scores.items(), key=lambda x: x[1], reverse=True)
        for num, _ in sorted_nums:
            selected.add(num)
            if len(selected) >= count:
                break

    # 补齐 (万一策略选不够)
    if len(selected) < count:
        remaining = [n for n in range(1, red_max + 1) if n not in selected]
        random.shuffle(remaining)
        for n in remaining:
            selected.add(n)
            if len(selected) >= count:
                break

    return sorted(selected)


def select_blue_numbers(data, lottery_type, analysis, strategy="balanced", count=None):
    """根据策略选择蓝球/后区号码"""
    cfg = LOTTERY_CONFIG[lottery_type]
    if count is None:
        count = cfg.get("blue_count", cfg.get("back_count", 1))
    blue_max = cfg["blue_max"]
    freq = analysis["frequency"]["blue"]
    missing = analysis["missing"]["blue"]

    scores = {}
    for i in range(1, blue_max + 1):
        f_item = next((x for x in freq if x["num"] == i), {"count": 0, "pct": 0})
        m_item = next((x for x in missing if x["num"] == i), {"missing": 0, "avg_gap": 0, "ratio": 0})
        scores[i] = {
            "freq": f_item["count"],
            "missing": m_item["missing"],
            "ratio": m_item["ratio"],
        }

    selected = set()

    if strategy == "hot":
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["freq"], reverse=True)
    elif strategy == "cold" or strategy == "missing":
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["ratio"], reverse=True)
    else:
        # balanced: 频率 + 遗漏综合 + 随机
        for num in scores:
            scores[num]["smart"] = scores[num]["freq"] * 0.3 + scores[num]["ratio"] * 30 + random.random() * 20
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["smart"], reverse=True)

    for num, _ in sorted_nums:
        selected.add(num)
        if len(selected) >= count:
            break

    return sorted(selected)


def apply_filters(combination, analysis, lottery_type):
    """对候选组合进行条件过滤，返回是否通过及得分"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    balls = combination["red"]
    score = 100
    passed = True
    reasons = []

    # 和值范围检查
    s = sum(balls)
    sum_info = analysis["sum"]
    sum_avg = sum_info["avg"]
    sum_min = sum_info["min"]
    sum_max = sum_info["max"]
    if s < sum_min or s > sum_max:
        score -= 20
        reasons.append(f"和值{s}超出范围[{sum_min}-{sum_max}]")
    elif abs(s - sum_avg) > 20:
        score -= 10
        reasons.append(f"和值{s}偏离均值{sum_avg}")

    # 跨度检查
    span = max(balls) - min(balls)
    span_info = analysis["span"]
    if span < span_info["min"]:
        score -= 15
        reasons.append(f"跨度{span}过小")

    # 奇偶比检查
    odd = sum(1 for n in balls if n % 2 == 1)
    even = len(balls) - odd
    oe = f"{odd}:{even}"
    oe_dist = analysis["odd_even"]["distribution"]
    if oe not in list(oe_dist.keys())[:5]:
        score -= 10
        reasons.append(f"奇偶比{oe}不常见")

    # 连号检查 (不超过2组连号)
    sorted_balls = sorted(balls)
    consec = sum(1 for i in range(len(sorted_balls) - 1) if sorted_balls[i + 1] - sorted_balls[i] == 1)
    if consec > 2:
        score -= 15
        reasons.append(f"连号{consec}组过多")

    # AC值检查
    diffs = set()
    for i in range(len(balls)):
        for j in range(i + 1, len(balls)):
            diffs.add(balls[j] - balls[i])
    ac = len(diffs) - (len(balls) - 1)
    ac_dist = analysis["ac"]["distribution"]
    if ac_dist:
        common_ac = list(ac_dist.keys())[:5]
        if str(ac) not in [str(a) for a in common_ac]:
            score -= 10
            reasons.append(f"AC值{ac}不常见")

    if score < 60:
        passed = False

    combination["score"] = max(score, 0)
    combination["reasons"] = reasons
    combination["stats"] = {
        "sum": s,
        "span": span,
        "odd_even": oe,
        "consecutive": consec,
        "ac": ac,
    }
    return passed


def generate_combinations(data, lottery_type, num_combos=5, strategy="balanced",
                          apply_filter=True, periods=50):
    """生成多注候选号码"""
    cfg = LOTTERY_CONFIG[lottery_type]
    analysis = full_analysis(data, lottery_type, periods)
    red_key = cfg["red_key"]
    blue_key = cfg["blue_key"]
    red_count = cfg.get("red_count", cfg.get("front_count", 5))
    blue_count = cfg.get("blue_count", cfg.get("back_count", 1))

    strategies_pool = ["hot", "cold", "missing", "balanced", "smart"] if strategy == "mixed" else [strategy] * num_combos

    results = []
    seen = set()

    for i in range(num_combos * 3):  # 多生成一些，过滤后取top
        strat = strategies_pool[i % len(strategies_pool)]
        red = select_red_numbers(data, lottery_type, analysis, strat, red_count)
        blue = select_blue_numbers(data, lottery_type, analysis, strat, blue_count)

        combo_key = tuple(red) + tuple(blue)
        if combo_key in seen:
            continue
        seen.add(combo_key)

        combo = {
            "red": red,
            "blue": list(blue) if not isinstance(blue, list) else blue,
            "strategy": strat,
        }

        if apply_filter:
            if apply_filters(combo, analysis, lottery_type):
                results.append(combo)
        else:
            combo["score"] = 100
            combo["reasons"] = []
            results.append(combo)

        if len(results) >= num_combos:
            break

    # 按分数排序
    results.sort(key=lambda x: x.get("score", 0), reverse=True)
    return results[:num_combos]


if __name__ == "__main__":
    from scraper import get_ssq_data, get_dlt_data

    print("=== 双色球选号 ===")
    ssq_data = get_ssq_data(limit=200)
    combos = generate_combinations(ssq_data, "ssq", num_combos=5, strategy="mixed")
    for i, c in enumerate(combos, 1):
        print(f"  第{i}注 [{c['strategy']}]: 红 {c['red']} 蓝 {c['blue']}  "
              f"分数:{c['score']} 和值:{c['stats']['sum']} 跨度:{c['stats']['span']} "
              f"奇偶:{c['stats']['odd_even']} AC:{c['stats']['ac']}")

    print(f"\n=== 大乐透选号 ===")
    dlt_data = get_dlt_data(limit=200)
    combos = generate_combinations(dlt_data, "dlt", num_combos=5, strategy="mixed")
    for i, c in enumerate(combos, 1):
        print(f"  第{i}注 [{c['strategy']}]: 前 {c['red']} 后 {c['blue']}  "
              f"分数:{c['score']} 和值:{c['stats']['sum']} 跨度:{c['stats']['span']} "
              f"奇偶:{c['stats']['odd_even']} AC:{c['stats']['ac']}")
