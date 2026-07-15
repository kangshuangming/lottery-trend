# -*- coding: utf-8 -*-
"""
彩票走势分析系统 - Flask后端
API: /api/data, /api/analysis, /api/select, /api/purchase
"""

from flask import Flask, jsonify, request, send_from_directory
from scraper import get_ssq_data, get_dlt_data
from analyzer import full_analysis, LOTTERY_CONFIG
from selector import generate_combinations
from purchase import (
    add_purchase, add_purchase_batch, get_purchases, delete_purchase,
    update_purchase_issue,
    check_purchase, check_all_purchases, get_win_summary, generate_improvement_suggestions,
    check_draw_status, get_draw_schedule, get_next_draw_time
)
import os

app = Flask(__name__, static_folder="static", static_url_path="/static")


def get_data(lottery_type, refresh=False, limit=500):
    """从 scraper 获取数据，scraper 内部已管理文件缓存，避免 Flask 内存缓存与文件不同步。"""
    if lottery_type == "ssq":
        return get_ssq_data(force_refresh=refresh, limit=limit)
    else:
        return get_dlt_data(force_refresh=refresh, limit=limit)


@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


@app.route("/api/data/<lottery_type>")
def api_data(lottery_type):
    """获取最近开奖数据"""
    refresh = request.args.get("refresh", "0") == "1"
    limit = int(request.args.get("limit", 500))
    data = get_data(lottery_type, refresh, limit)
    count = int(request.args.get("count", 30))
    return jsonify({"data": data[:count], "total": len(data)})


@app.route("/api/analysis/<lottery_type>")
def api_analysis(lottery_type):
    """获取全量分析数据"""
    refresh = request.args.get("refresh", "0") == "1"
    periods = int(request.args.get("periods", 50))
    data = get_data(lottery_type, refresh)
    analysis = full_analysis(data, lottery_type, periods)
    return jsonify(analysis)


@app.route("/api/select/<lottery_type>")
def api_select(lottery_type):
    """智能选号"""
    refresh = request.args.get("refresh", "0") == "1"
    strategy = request.args.get("strategy", "mixed")
    count = int(request.args.get("count", 5))
    periods = int(request.args.get("periods", 50))
    use_filter = request.args.get("filter", "1") == "1"

    data = get_data(lottery_type, refresh)
    combos = generate_combinations(data, lottery_type, count, strategy, use_filter, periods)
    return jsonify({"combos": combos})


# ========== 购买记录 API ==========

@app.route("/api/purchase", methods=["POST"])
def api_purchase():
    """添加单条购买记录"""
    data = request.get_json() or {}
    required = ["lottery_type", "issue", "red", "blue"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"缺少参数: {field}"}), 400

    record = add_purchase(
        lottery_type=data["lottery_type"],
        issue=data["issue"],
        red=data["red"],
        blue=data["blue"],
        strategy=data.get("strategy", ""),
        source=data.get("source", "user"),
        cost=data.get("cost", 2.0),
        note=data.get("note", ""),
    )
    return jsonify({"success": True, "record": record})


@app.route("/api/purchase/batch", methods=["POST"])
def api_purchase_batch():
    """批量添加购买记录"""
    data = request.get_json() or {}
    records = data.get("records", [])
    if not records:
        return jsonify({"error": "records 不能为空"}), 400

    results = add_purchase_batch(records)
    return jsonify({"success": True, "records": results, "count": len(results)})


@app.route("/api/purchases")
def api_purchases():
    """获取购买记录"""
    lottery_type = request.args.get("lottery_type")
    status = request.args.get("status")
    issue = request.args.get("issue")
    purchases = get_purchases(lottery_type=lottery_type, status=status, issue=issue)
    return jsonify({
        "purchases": purchases,
        "summary": get_win_summary(),
    })


@app.route("/api/purchase/<purchase_id>", methods=["DELETE"])
def api_delete_purchase(purchase_id):
    """删除购买记录"""
    delete_purchase(purchase_id)
    return jsonify({"success": True})


@app.route("/api/purchase/<purchase_id>", methods=["PATCH"])
def api_update_purchase(purchase_id):
    """修改购买记录的期号，并重置对比状态"""
    data = request.get_json(silent=True) or {}
    new_issue = data.get("issue")
    if not new_issue:
        return jsonify({"error": "缺少参数: issue"}), 400
    record = update_purchase_issue(purchase_id, new_issue)
    if record is None:
        return jsonify({"error": "记录不存在"}), 404
    return jsonify({"success": True, "record": record})


@app.route("/api/purchases/issue", methods=["POST"])
def api_update_purchases_issue():
    """批量修改购买记录的期号，并重置对比状态"""
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    new_issue = data.get("issue")
    if not ids or not new_issue:
        return jsonify({"error": "缺少参数: ids 或 issue"}), 400
    updated = []
    not_found = []
    for pid in ids:
        record = update_purchase_issue(pid, new_issue)
        if record is None:
            not_found.append(pid)
        else:
            updated.append(record)
    return jsonify({
        "success": True,
        "updated_count": len(updated),
        "not_found": not_found,
    })


@app.route("/api/check/<purchase_id>", methods=["POST"])
def api_check_purchase(purchase_id):
    """检查单条购买记录是否中奖"""
    data = request.get_json(silent=True) or {}
    draw_data = data.get("draw_data")  # 可选: 手动传入开奖号码
    result = check_purchase(purchase_id, draw_data=draw_data)
    if result is None:
        return jsonify({"error": "记录不存在"}), 404
    if "error" in result:
        return jsonify({"error": result["error"]}), 400
    not_drawn = result.get("not_drawn", False)
    return jsonify({"success": True, "record": result, "not_drawn": not_drawn})


@app.route("/api/check-all", methods=["POST"])
def api_check_all():
    """批量检查所有待开奖记录"""
    data = request.get_json(silent=True) or {}
    lottery_type = data.get("lottery_type")
    issue = data.get("issue")
    results, drawn_count, not_drawn_count = check_all_purchases(lottery_type=lottery_type, issue=issue)
    return jsonify({
        "success": True,
        "records": results,
        "count": len(results),
        "drawn_count": drawn_count,
        "not_drawn_count": not_drawn_count,
    })


@app.route("/api/summary")
def api_summary():
    """获取中奖统计汇总"""
    return jsonify(get_win_summary())


@app.route("/api/suggestions")
def api_suggestions():
    """获取改进建议"""
    purchase_id = request.args.get("purchase_id")
    lottery_type = request.args.get("lottery_type")
    periods = int(request.args.get("periods", 50))
    result = generate_improvement_suggestions(
        purchase_id=purchase_id,
        lottery_type=lottery_type,
        periods=periods,
    )
    return jsonify(result)


@app.route("/api/latest-issue/<lottery_type>")
def api_latest_issue(lottery_type):
    """获取最新开奖期号及建议购买期号"""
    data = get_data(lottery_type)
    if not data:
        return jsonify({"error": "无数据"}), 404
    latest = data[0]
    next_issue = str(int(latest["issue"]) + 1).zfill(len(latest["issue"]))

    schedule = get_draw_schedule(lottery_type)
    next_draw = get_next_draw_time(lottery_type)

    return jsonify({
        "latest_issue": latest["issue"],
        "latest_date": latest["date"],
        "suggested_issue": next_issue,
        "draw_schedule": schedule,
        "next_draw_time": next_draw.strftime("%Y-%m-%d %H:%M") if next_draw else None,
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5088))
    # 启动时预加载数据
    print("正在预加载数据...")
    get_data("ssq")
    get_data("dlt")
    print(f"数据加载完成，启动服务: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
