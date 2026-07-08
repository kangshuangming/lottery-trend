# -*- coding: utf-8 -*-
"""
彩票历史数据抓取模块
数据来源: 500.com (datachart.500.com)
支持: 双色球(SSQ) + 大乐透(DLT)
"""

import json
import os
import time
import requests
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(BASE_DIR, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SSQ_URL = "https://datachart.500.com/ssq/history/newinc/history.php"
DLT_URL = "https://datachart.500.com/dlt/history/newinc/history.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://datachart.500.com/",
}


def fetch_ssq(limit=500):
    """抓取双色球历史数据
    红球1-33选6, 蓝球1-16选1
    返回: [{issue, date, red:[6], blue:int}, ...]
    """
    params = {"limit": limit}
    resp = requests.get(SSQ_URL, params=params, headers=HEADERS, timeout=15)
    resp.encoding = "gb2312"
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for tr in soup.select("tr.t_tr1"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue
        issue = tds[0].get_text(strip=True)
        if not issue or not issue.isdigit():
            continue

        # 红球: tds[1]-tds[6], class="t_cfont2"
        red_balls = []
        for i in range(1, 7):
            num = tds[i].get_text(strip=True)
            if num.isdigit():
                red_balls.append(int(num))

        # 蓝球: tds[7], class="t_cfont4"
        blue_ball = None
        blue_text = tds[7].get_text(strip=True)
        if blue_text.isdigit():
            blue_ball = int(blue_text)

        # 日期: 最后一个td
        date_str = tds[-1].get_text(strip=True)

        if len(red_balls) == 6 and blue_ball is not None:
            results.append({
                "issue": issue,
                "date": date_str,
                "red": sorted(red_balls),
                "blue": blue_ball,
            })

    return results


def fetch_dlt(limit=500):
    """抓取大乐透历史数据
    前区1-35选5, 后区1-12选2
    返回: [{issue, date, front:[5], back:[2]}, ...]
    """
    params = {"limit": limit}
    resp = requests.get(DLT_URL, params=params, headers=HEADERS, timeout=15)
    resp.encoding = "gb2312"
    soup = BeautifulSoup(resp.text, "html.parser")

    results = []
    for tr in soup.select("tr.t_tr1"):
        tds = tr.find_all("td")
        if len(tds) < 8:
            continue
        issue = tds[0].get_text(strip=True)
        if not issue or not issue.isdigit():
            continue

        # 前区: tds[1]-tds[5], class="cfont2"
        front_balls = []
        for i in range(1, 6):
            num = tds[i].get_text(strip=True)
            if num.isdigit():
                front_balls.append(int(num))

        # 后区: tds[6]-tds[7], class="cfont4"
        back_balls = []
        for i in range(6, 8):
            num = tds[i].get_text(strip=True)
            if num.isdigit():
                back_balls.append(int(num))

        # 日期: 最后一个td
        date_str = tds[-1].get_text(strip=True)

        if len(front_balls) == 5 and len(back_balls) == 2:
            results.append({
                "issue": issue,
                "date": date_str,
                "front": sorted(front_balls),
                "back": sorted(back_balls),
            })

    return results


def get_ssq_data(force_refresh=False, limit=500):
    """获取双色球数据（带缓存，6小时有效期）"""
    cache_file = os.path.join(CACHE_DIR, "ssq_data.json")
    if not force_refresh and os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < 6 * 3600:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    data = fetch_ssq(limit=limit)
    if data:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[SSQ] 抓取完成: {len(data)} 期")
    return data


def get_dlt_data(force_refresh=False, limit=500):
    """获取大乐透数据（带缓存，6小时有效期）"""
    cache_file = os.path.join(CACHE_DIR, "dlt_data.json")
    if not force_refresh and os.path.exists(cache_file):
        mtime = os.path.getmtime(cache_file)
        if time.time() - mtime < 6 * 3600:
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)

    data = fetch_dlt(limit=limit)
    if data:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"[DLT] 抓取完成: {len(data)} 期")
    return data


if __name__ == "__main__":
    print("=== 双色球 ===")
    ssq = get_ssq_data(force_refresh=True, limit=30)
    for d in ssq[:5]:
        print(f"  {d['issue']} | {d['date']} | 红:{d['red']} 蓝:{d['blue']}")

    print(f"\n=== 大乐透 ===")
    dlt = get_dlt_data(force_refresh=True, limit=30)
    for d in dlt[:5]:
        print(f"  {d['issue']} | {d['date']} | 前:{d['front']} 后:{d['back']}")
