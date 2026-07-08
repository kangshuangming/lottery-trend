# -*- coding: utf-8 -*-
"""
彩票走势分析引擎
支持: 双色球(SSQ) + 大乐透(DLT)
分析维度: 频率/遗漏/和值/跨度/奇偶比/大小比/三分区/重号/连号/AC值/冷热号/尾数/质合
"""

from collections import Counter, defaultdict
import math

# 彩种配置
LOTTERY_CONFIG = {
    "ssq": {
        "name": "双色球",
        "red_max": 33,
        "red_count": 6,
        "blue_max": 16,
        "blue_count": 1,
        "red_key": "red",
        "blue_key": "blue",
        "small_threshold": 17,  # 1-16小, 17-33大
    },
    "dlt": {
        "name": "大乐透",
        "red_max": 35,
        "red_count": 5,
        "blue_max": 12,
        "blue_count": 2,
        "red_key": "front",
        "blue_key": "back",
        "small_threshold": 18,  # 1-17小, 18-35大
    },
}

PRIMES = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31}


def analyze_frequency(data, lottery_type, periods=50):
    """频率分析: 每个号码在最近N期出现的次数"""
    cfg = LOTTERY_CONFIG[lottery_type]
    recent = data[:periods]
    red_key = cfg["red_key"]
    red_max = cfg["red_max"]
    blue_key = cfg["blue_key"]
    blue_max = cfg["blue_max"]

    red_freq = Counter()
    blue_freq = Counter()

    for draw in recent:
        for num in draw[red_key]:
            red_freq[num] += 1
        if isinstance(draw[blue_key], list):
            for num in draw[blue_key]:
                blue_freq[num] += 1
        else:
            blue_freq[draw[blue_key]] += 1

    # 构建完整频率表 (含0次)
    red_result = []
    for i in range(1, red_max + 1):
        cnt = red_freq.get(i, 0)
        red_result.append({"num": i, "count": cnt, "pct": round(cnt / len(recent) * 100, 1)})

    blue_result = []
    for i in range(1, blue_max + 1):
        cnt = blue_freq.get(i, 0)
        blue_result.append({"num": i, "count": cnt, "pct": round(cnt / len(recent) * 100, 1)})

    return {"red": red_result, "blue": blue_result}


def analyze_missing(data, lottery_type):
    """遗漏分析: 每个号码距离上次出现的期数"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    red_max = cfg["red_max"]
    blue_key = cfg["blue_key"]
    blue_max = cfg["blue_max"]

    red_missing = {i: len(data) for i in range(1, red_max + 1)}
    blue_missing = {i: len(data) for i in range(1, blue_max + 1)}

    for idx, draw in enumerate(data):
        for num in draw[red_key]:
            if red_missing[num] == len(data):
                red_missing[num] = idx
        if isinstance(draw[blue_key], list):
            for num in draw[blue_key]:
                if blue_missing[num] == len(data):
                    blue_missing[num] = idx
        else:
            if blue_missing[draw[blue_key]] == len(data):
                blue_missing[draw[blue_key]] = idx

    # 计算平均遗漏 (历史平均间隔)
    red_avg_gap = {}
    for num in range(1, red_max + 1):
        positions = [i for i, d in enumerate(data) if num in d[red_key]]
        if len(positions) >= 2:
            gaps = [positions[j] - positions[j - 1] for j in range(1, len(positions))]
            red_avg_gap[num] = round(sum(gaps) / len(gaps), 1)
        else:
            red_avg_gap[num] = 0

    blue_avg_gap = {}
    for num in range(1, blue_max + 1):
        if isinstance(data[0][blue_key], list):
            positions = [i for i, d in enumerate(data) if num in d[blue_key]]
        else:
            positions = [i for i, d in enumerate(data) if d[blue_key] == num]
        if len(positions) >= 2:
            gaps = [positions[j] - positions[j - 1] for j in range(1, len(positions))]
            blue_avg_gap[num] = round(sum(gaps) / len(gaps), 1)
        else:
            blue_avg_gap[num] = 0

    red_result = []
    for i in range(1, red_max + 1):
        miss = red_missing[i]
        avg = red_avg_gap[i]
        ratio = round(miss / avg, 2) if avg > 0 else 0
        red_result.append({"num": i, "missing": miss, "avg_gap": avg, "ratio": ratio})

    blue_result = []
    for i in range(1, blue_max + 1):
        miss = blue_missing[i]
        avg = blue_avg_gap[i]
        ratio = round(miss / avg, 2) if avg > 0 else 0
        blue_result.append({"num": i, "missing": miss, "avg_gap": avg, "ratio": ratio})

    return {"red": red_result, "blue": blue_result}


def analyze_sum(data, lottery_type, periods=50):
    """和值分析: 最近N期红球和值走势"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    sums = []
    for draw in recent:
        s = sum(draw[red_key])
        sums.append(s)

    return {
        "values": sums,
        "avg": round(sum(sums) / len(sums), 1) if sums else 0,
        "min": min(sums) if sums else 0,
        "max": max(sums) if sums else 0,
        "last5": sums[:5],
    }


def analyze_span(data, lottery_type, periods=50):
    """跨度分析: max - min"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    spans = []
    for draw in recent:
        sp = max(draw[red_key]) - min(draw[red_key])
        spans.append(sp)

    return {
        "values": spans,
        "avg": round(sum(spans) / len(spans), 1) if spans else 0,
        "min": min(spans) if spans else 0,
        "max": max(spans) if spans else 0,
        "last5": spans[:5],
    }


def analyze_odd_even(data, lottery_type, periods=50):
    """奇偶比分析"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    ratios = []
    for draw in recent:
        odd = sum(1 for n in draw[red_key] if n % 2 == 1)
        even = len(draw[red_key]) - odd
        ratios.append(f"{odd}:{even}")

    # 统计各比例出现次数
    ratio_dist = Counter(ratios)
    return {
        "values": ratios[:20],
        "distribution": dict(ratio_dist.most_common()),
        "last": ratios[0] if ratios else "0:0",
    }


def analyze_big_small(data, lottery_type, periods=50):
    """大小比分析"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    threshold = cfg["small_threshold"]
    recent = data[:periods]

    ratios = []
    for draw in recent:
        small = sum(1 for n in draw[red_key] if n < threshold)
        big = len(draw[red_key]) - small
        ratios.append(f"{big}:{small}")

    ratio_dist = Counter(ratios)
    return {
        "values": ratios[:20],
        "distribution": dict(ratio_dist.most_common()),
        "last": ratios[0] if ratios else "0:0",
    }


def analyze_zone(data, lottery_type, periods=50):
    """三分区分析 (低/中/高)"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    red_max = cfg["red_max"]
    zone_size = red_max // 3
    recent = data[:periods]

    zones = []
    for draw in recent:
        z1 = sum(1 for n in draw[red_key] if n <= zone_size)
        z2 = sum(1 for n in draw[red_key] if zone_size < n <= zone_size * 2)
        z3 = len(draw[red_key]) - z1 - z2
        zones.append(f"{z1}:{z2}:{z3}")

    zone_dist = Counter(zones)
    return {
        "values": zones[:20],
        "distribution": dict(zone_dist.most_common(10)),
        "last": zones[0] if zones else "0:0:0",
        "zone_ranges": f"1-{zone_size}/{zone_size+1}-{zone_size*2}/{zone_size*2+1}-{red_max}",
    }


def analyze_repeat(data, lottery_type, periods=50):
    """重号分析: 与上期重复的号码数"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods + 1] if len(data) > periods else data[:]

    repeats = []
    for i in range(len(recent) - 1):
        prev_set = set(recent[i + 1][red_key])
        curr_set = set(recent[i][red_key])
        overlap = prev_set & curr_set
        repeats.append(len(overlap))

    repeat_dist = Counter(repeats)
    return {
        "values": repeats[:20],
        "distribution": dict(sorted(repeat_dist.items())),
        "avg": round(sum(repeats) / len(repeats), 2) if repeats else 0,
        "last": repeats[0] if repeats else 0,
    }


def analyze_consecutive(data, lottery_type, periods=50):
    """连号分析: 一注中连续号码的对数"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    consecutives = []
    for draw in recent:
        balls = sorted(draw[red_key])
        consec = sum(1 for i in range(len(balls) - 1) if balls[i + 1] - balls[i] == 1)
        consecutives.append(consec)

    consec_dist = Counter(consecutives)
    return {
        "values": consecutives[:20],
        "distribution": dict(sorted(consec_dist.items())),
        "avg": round(sum(consecutives) / len(consecutives), 2) if consecutives else 0,
        "last": consecutives[0] if consecutives else 0,
    }


def analyze_ac(data, lottery_type, periods=50):
    """AC值分析: 号码算术复杂度
    AC = 不同差值数 - (号码数 - 1)
    """
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    ac_values = []
    for draw in recent:
        balls = sorted(draw[red_key])
        diffs = set()
        for i in range(len(balls)):
            for j in range(i + 1, len(balls)):
                diffs.add(balls[j] - balls[i])
        ac = len(diffs) - (len(balls) - 1)
        ac_values.append(ac)

    ac_dist = Counter(ac_values)
    return {
        "values": ac_values[:20],
        "distribution": dict(sorted(ac_dist.items())),
        "avg": round(sum(ac_values) / len(ac_values), 2) if ac_values else 0,
        "last": ac_values[0] if ac_values else 0,
    }


def analyze_hot_cold(data, lottery_type, periods=50):
    """冷热号分析: 基于频率划分热号/温号/冷号"""
    freq = analyze_frequency(data, lottery_type, periods)
    cfg = LOTTERY_CONFIG[lottery_type]
    red_freq = freq["red"]
    counts = [r["count"] for r in red_freq]
    if not counts:
        return {"hot": [], "warm": [], "cold": []}

    avg_count = sum(counts) / len(counts)
    hot_threshold = avg_count * 1.3
    cold_threshold = avg_count * 0.5

    hot = [r["num"] for r in red_freq if r["count"] >= hot_threshold]
    warm = [r["num"] for r in red_freq if cold_threshold <= r["count"] < hot_threshold]
    cold = [r["num"] for r in red_freq if r["count"] < cold_threshold]

    return {
        "hot": sorted(hot),
        "warm": sorted(warm),
        "cold": sorted(cold),
        "hot_count": len(hot),
        "warm_count": len(warm),
        "cold_count": len(cold),
    }


def analyze_tail(data, lottery_type, periods=50):
    """尾数分布分析"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    tail_counter = Counter()
    for draw in recent:
        for num in draw[red_key]:
            tail_counter[num % 10] += 1

    result = []
    for t in range(10):
        result.append({"tail": t, "count": tail_counter.get(t, 0)})

    return {"distribution": result}


def analyze_prime(data, lottery_type, periods=50):
    """质合比分析"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    recent = data[:periods]

    ratios = []
    for draw in recent:
        prime = sum(1 for n in draw[red_key] if n in PRIMES)
        composite = len(draw[red_key]) - prime
        ratios.append(f"{prime}:{composite}")

    ratio_dist = Counter(ratios)
    return {
        "values": ratios[:20],
        "distribution": dict(ratio_dist.most_common()),
        "last": ratios[0] if ratios else "0:0",
    }


def analyze_recent_trend(data, lottery_type, periods=30):
    """近N期号码走势 (用于走势图)"""
    cfg = LOTTERY_CONFIG[lottery_type]
    red_key = cfg["red_key"]
    blue_key = cfg["blue_key"]
    recent = data[:periods]

    trend = []
    for draw in recent:
        entry = {
            "issue": draw["issue"],
            "date": draw["date"],
            "red": draw[red_key],
        }
        if isinstance(draw[blue_key], list):
            entry["blue"] = draw[blue_key]
        else:
            entry["blue"] = [draw[blue_key]]
        trend.append(entry)

    return trend


def full_analysis(data, lottery_type, periods=50):
    """全量分析 - 一次返回所有分析结果"""
    return {
        "frequency": analyze_frequency(data, lottery_type, periods),
        "missing": analyze_missing(data, lottery_type),
        "sum": analyze_sum(data, lottery_type, periods),
        "span": analyze_span(data, lottery_type, periods),
        "odd_even": analyze_odd_even(data, lottery_type, periods),
        "big_small": analyze_big_small(data, lottery_type, periods),
        "zone": analyze_zone(data, lottery_type, periods),
        "repeat": analyze_repeat(data, lottery_type, periods),
        "consecutive": analyze_consecutive(data, lottery_type, periods),
        "ac": analyze_ac(data, lottery_type, periods),
        "hot_cold": analyze_hot_cold(data, lottery_type, periods),
        "tail": analyze_tail(data, lottery_type, periods),
        "prime": analyze_prime(data, lottery_type, periods),
        "trend": analyze_recent_trend(data, lottery_type, min(periods, 30)),
        "total_periods": len(data),
        "analysis_periods": periods,
    }
