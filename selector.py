# -*- coding: utf-8 -*-
"""
智能选号引擎 v2
基于走势分析结果，多策略组合选号
策略: 热号追势 / 冷号回补 / 遗漏回补 / 均衡组合 / 智能评分

v2 改进:
- 红/蓝球选择加入加权随机，避免不同策略产出雷同号码
- 蓝球去重: 同一蓝球在5注中最多出现2次
- 注间多样性: 任意两注重复红球不超过3个
- 和值偏离均值25+额外扣分
- 连号0组时轻微加分(更自然), 1-2组不扣分
"""

import random
from analyzer import full_analysis, LOTTERY_CONFIG


def _weighted_sample(candidates, weights, count):
    """加权随机采样，从candidates中按weights概率选count个"""
    if len(candidates) <= count:
        return list(candidates)
    # 归一化权重
    total = sum(weights) or 1
    probs = [w / total for w in weights]
    # 使用random.choices确保概率分布
    chosen = set()
    pool = list(zip(candidates, probs))
    while len(chosen) < count and pool:
        nums = [n for n, _ in pool]
        ps = [p for _, p in pool]
        pick = random.choices(nums, weights=ps, k=1)[0]
        chosen.add(pick)
        pool = [(n, p) for n, p in pool if n != pick]
    return sorted(chosen)


def select_red_numbers(data, lottery_type, analysis, strategy="balanced", count=None, exclude=None):
    """根据策略选择红球号码 (v2: 加权随机 + 排除已选号码)"""
    cfg = LOTTERY_CONFIG[lottery_type]
    if count is None:
        count = cfg["red_count"] if "red_count" in cfg else cfg["front_count"]
    red_max = cfg["red_max"]
    freq = analysis["frequency"]["red"]
    missing = analysis["missing"]["red"]
    hot_cold = analysis["hot_cold"]
    exclude = exclude or set()

    # 构建号码评分
    scores = {}
    for i in range(1, red_max + 1):
        f_item = next((x for x in freq if x["num"] == i), {"count": 0, "pct": 0})
        m_item = next((x for x in missing if x["num"] == i), {"missing": 0, "avg_gap": 0, "ratio": 0})
        scores[i] = {
            "freq": f_item["count"],
            "missing": m_item["missing"],
            "ratio": m_item["ratio"],
            "is_hot": i in hot_cold["hot"],
            "is_cold": i in hot_cold["cold"],
        }

    selected = set()

    if strategy == "hot":
        # 热号追势: 从频率前12名中加权随机选6个
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["freq"], reverse=True)
        top_pool = [n for n, _ in sorted_nums[:12] if n not in exclude]
        weights = [max(scores[n]["freq"], 1) for n in top_pool]
        selected.update(_weighted_sample(top_pool, weights, count))

    elif strategy == "cold":
        # 冷号回补: 从遗漏比前12名中加权随机选6个
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["ratio"], reverse=True)
        top_pool = [n for n, _ in sorted_nums[:12] if n not in exclude]
        weights = [max(scores[n]["ratio"], 0.1) for n in top_pool]
        selected.update(_weighted_sample(top_pool, weights, count))

    elif strategy == "missing":
        # 遗漏回补: 从遗漏期数前12名中加权随机选6个
        sorted_nums = sorted(scores.items(), key=lambda x: x[1]["missing"], reverse=True)
        top_pool = [n for n, _ in sorted_nums[:12] if n not in exclude]
        weights = [max(scores[n]["missing"], 1) for n in top_pool]
        selected.update(_weighted_sample(top_pool, weights, count))

    elif strategy == "balanced":
        # 均衡组合: 2热+2温+2冷 (随机化)
        hot = [n for n in hot_cold["hot"] if n not in exclude]
        warm = [n for n in hot_cold["warm"] if n not in exclude]
        cold = [n for n in hot_cold["cold"] if n not in exclude]

        random.shuffle(hot)
        random.shuffle(warm)
        random.shuffle(cold)

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
        all_remaining = [n for n in range(1, red_max + 1) if n not in selected and n not in exclude]
        random.shuffle(all_remaining)
        for n in all_remaining:
            if len(selected) >= count:
                break
            selected.add(n)

    elif strategy == "smart":
        # 智能评分: 综合频率 + 遗漏比 + 随机扰动
        smart_scores = {}
        for num, info in scores.items():
            if num in exclude:
                continue
            max_freq = max(s["freq"] for s in scores.values()) or 1
            freq_s = info["freq"] / max_freq * 40
            ratio_s = min(info["ratio"] / 2, 1) * 30
            rand_s = random.random() * 30
            smart_scores[num] = freq_s + ratio_s + rand_s

        sorted_nums = sorted(smart_scores.items(), key=lambda x: x[1], reverse=True)
        for num, _ in sorted_nums:
            selected.add(num)
            if len(selected) >= count:
                break

    # 补齐
    if len(selected) < count:
        remaining = [n for n in range(1, red_max + 1) if n not in selected and n not in exclude]
        random.shuffle(remaining)
        for n in remaining:
            selected.add(n)
            if len(selected) >= count:
                break

    return sorted(selected)


def select_blue_numbers(data, lottery_type, analysis, strategy="balanced", count=None, exclude=None):
    """根据策略选择蓝球/后区号码 (v2: 加权随机 + 排除已选蓝球)"""
    cfg = LOTTERY_CONFIG[lottery_type]
    if count is None:
        count = cfg.get("blue_count", cfg.get("back_count", 1))
    blue_max = cfg["blue_max"]
    freq = analysis["frequency"]["blue"]
    missing = analysis["missing"]["blue"]
    exclude = exclude or set()

    scores = {}
    for i in range(1, blue_max + 1):
        f_item = next((x for x in freq if x["num"] == i), {"count": 0, "pct": 0})
        m_item = next((x for x in missing if x["num"] == i), {"missing": 0, "avg_gap": 0, "ratio": 0})
        scores[i] = {
            "freq": f_item["count"],
            "missing": m_item["missing"],
            "ratio": m_item["ratio"],
        }

    # 构建候选池 (排除已用过多的蓝球)
    candidates = [i for i in range(1, blue_max + 1) if i not in exclude]

    if strategy == "hot":
        # 热号: 从频率前6名中加权随机选
        sorted_nums = sorted([(i, scores[i]) for i in candidates], key=lambda x: x[1]["freq"], reverse=True)
        top_pool = [n for n, _ in sorted_nums[:6]]
        weights = [max(scores[n]["freq"], 1) for n in top_pool]
        return _weighted_sample(top_pool, weights, count)

    elif strategy == "cold" or strategy == "missing":
        # 冷号/遗漏: 从遗漏比前6名中加权随机选
        if strategy == "cold":
            key_fn = lambda x: x[1]["ratio"]
        else:
            key_fn = lambda x: x[1]["missing"]
        sorted_nums = sorted([(i, scores[i]) for i in candidates], key=key_fn, reverse=True)
        top_pool = [n for n, _ in sorted_nums[:6]]
        weights = [max(key_fn((n, scores[n])), 0.1) for n in top_pool]
        return _weighted_sample(top_pool, weights, count)

    else:
        # balanced/smart: 频率 + 遗漏综合 + 随机
        smart_scores = {}
        for num in candidates:
            freq_s = scores[num]["freq"] * 0.3
            ratio_s = scores[num]["ratio"] * 25
            rand_s = random.random() * 25
            smart_scores[num] = freq_s + ratio_s + rand_s
        sorted_nums = sorted(smart_scores.items(), key=lambda x: x[1], reverse=True)
        selected = []
        for num, _ in sorted_nums:
            selected.append(num)
            if len(selected) >= count:
                break
        return sorted(selected)


def apply_filters(combination, analysis, lottery_type):
    """对候选组合进行条件过滤，返回是否通过及得分 (v2: 更精细的评分)"""
    balls = combination["red"]
    score = 100
    passed = True
    reasons = []
    plus_reasons = []

    # 和值范围检查
    s = sum(balls)
    sum_info = analysis["sum"]
    sum_avg = sum_info["avg"]
    sum_min = sum_info["min"]
    sum_max = sum_info["max"]
    if s < sum_min or s > sum_max:
        score -= 25
        reasons.append(f"和值{s}超出历史范围[{sum_min}-{sum_max}]")
    else:
        dev = abs(s - sum_avg)
        if dev > 35:
            score -= 20
            reasons.append(f"和值{s}偏离均值{sum_avg}达{dev:.0f}")
        elif dev > 25:
            score -= 12
            reasons.append(f"和值{s}偏离均值{sum_avg}达{dev:.0f}")
        elif dev > 15:
            score -= 5
            reasons.append(f"和值{s}略偏离均值{sum_avg}")

    # 跨度检查
    span = max(balls) - min(balls)
    span_info = analysis["span"]
    if span < span_info["min"]:
        score -= 15
        reasons.append(f"跨度{span}过小")
    elif span < 15:
        score -= 8
        reasons.append(f"跨度{span}偏小")

    # 奇偶比检查
    odd = sum(1 for n in balls if n % 2 == 1)
    even = len(balls) - odd
    oe = f"{odd}:{even}"
    oe_dist = analysis["odd_even"]["distribution"]
    oe_keys = list(oe_dist.keys())
    if oe not in oe_keys[:5]:
        score -= 10
        reasons.append(f"奇偶比{oe}不常见")

    # 连号检查
    sorted_balls = sorted(balls)
    consec = sum(1 for i in range(len(sorted_balls) - 1) if sorted_balls[i + 1] - sorted_balls[i] == 1)
    if consec > 3:
        score -= 15
        reasons.append(f"连号{consec}组过多")
    elif consec >= 1 and consec <= 2:
        score += 5  # 1-2组连号是正常的，加分
        plus_reasons.append(f"连号{consec}组(正常范围)")

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

    # 三分区检查 (每个区至少有1个号码)
    cfg = LOTTERY_CONFIG[lottery_type]
    red_max = cfg["red_max"]
    zone_size = red_max // 3
    z1 = sum(1 for n in balls if n <= zone_size)
    z2 = sum(1 for n in balls if zone_size < n <= zone_size * 2)
    z3 = len(balls) - z1 - z2
    if z1 == 0 or z2 == 0 or z3 == 0:
        score -= 8
        reasons.append(f"三分区{z1}:{z2}:{z3}有空白区")

    if score < 55:
        passed = False

    combination["score"] = max(score, 0)
    combination["reasons"] = reasons
    combination["plus_reasons"] = plus_reasons
    combination["stats"] = {
        "sum": s,
        "span": span,
        "odd_even": oe,
        "consecutive": consec,
        "ac": ac,
    }
    return passed


def _count_overlap(red1, red2):
    """计算两组红球的重叠数"""
    return len(set(red1) & set(red2))


def generate_combinations(data, lottery_type, num_combos=5, strategy="balanced",
                          apply_filter=True, periods=50):
    """生成多注候选号码 (v2: 注间多样性 + 蓝球去重)"""
    cfg = LOTTERY_CONFIG[lottery_type]
    analysis = full_analysis(data, lottery_type, periods)
    red_count = cfg.get("red_count", cfg.get("front_count", 5))
    blue_count = cfg.get("blue_count", cfg.get("back_count", 1))

    strategies_pool = ["hot", "cold", "missing", "balanced", "smart"] if strategy == "mixed" else [strategy] * num_combos

    results = []
    seen = set()
    blue_usage = {}  # {blue_num: count} 蓝球使用次数
    max_blue_reuse = 2  # 同一蓝球最多用2次

    max_attempts = num_combos * 8
    for i in range(max_attempts):
        if len(results) >= num_combos:
            break

        strat = strategies_pool[i % len(strategies_pool)]

        # 计算需要排除的红球 (与已选组合重叠超过3个的红球暂不排除，而是在后续检查中跳过)
        # 计算需要排除的蓝球 (已用满max_blue_reuse次的)
        exclude_blue = {b for b, cnt in blue_usage.items() if cnt >= max_blue_reuse}

        # 尝试多次生成一个通过多样性检查的组合
        for retry in range(5):
            red = select_red_numbers(data, lottery_type, analysis, strat, red_count)
            blue = select_blue_numbers(data, lottery_type, analysis, strat, blue_count, exclude=exclude_blue)

            combo_key = tuple(red) + tuple(blue)
            if combo_key in seen:
                continue

            # 检查与已有组合的红球重叠
            too_similar = False
            for existing in results:
                overlap = _count_overlap(red, existing["red"])
                if overlap > 3:
                    too_similar = True
                    break

            if too_similar:
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
                    for b in (blue if isinstance(blue, list) else [blue]):
                        blue_usage[b] = blue_usage.get(b, 0) + 1
                    break
            else:
                combo["score"] = 100
                combo["reasons"] = []
                results.append(combo)
                for b in (blue if isinstance(blue, list) else [blue]):
                    blue_usage[b] = blue_usage.get(b, 0) + 1
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

    # 检查多样性
    print("\n  --- 多样性检查 ---")
    for i in range(len(combos)):
        for j in range(i + 1, len(combos)):
            overlap = _count_overlap(combos[i]["red"], combos[j]["red"])
            blue_same = set(combos[i]["blue"]) & set(combos[j]["blue"])
            print(f"  第{i+1}注 vs 第{j+1}注: 红球重叠{overlap}个, 蓝球{'相同' if blue_same else '不同'}")

    print(f"\n=== 大乐透选号 ===")
    dlt_data = get_dlt_data(limit=200)
    combos = generate_combinations(dlt_data, "dlt", num_combos=5, strategy="mixed")
    for i, c in enumerate(combos, 1):
        print(f"  第{i}注 [{c['strategy']}]: 前 {c['red']} 后 {c['blue']}  "
              f"分数:{c['score']} 和值:{c['stats']['sum']} 跨度:{c['stats']['span']} "
              f"奇偶:{c['stats']['odd_even']} AC:{c['stats']['ac']}")
