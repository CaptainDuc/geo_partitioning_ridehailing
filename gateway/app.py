from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Tuple

import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

SHARDS: Dict[str, Dict[str, str]] = {
    "eu_west": {
        "city": "Paris",
        "label": "EU-West",
        "url": "http://localhost:5001",
        "storage": os.path.join(ROOT_DIR, "shards", "eu_west", "storage.json"),
    },
    "eu_north": {
        "city": "London",
        "label": "EU-North",
        "url": "http://localhost:5002",
        "storage": os.path.join(ROOT_DIR, "shards", "eu_north", "storage.json"),
    },
}

CITY_TO_SHARD_KEY = {meta["city"]: key for key, meta in SHARDS.items()}


def shard_key_for_city(city: Optional[str]) -> Optional[str]:
    if not city:
        return None
    return CITY_TO_SHARD_KEY.get(city)


def safe_load_storage(path: str) -> list[dict[str, Any]]:
    if not os.path.exists(path):
        return []

    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def shard_records(shard_key: str) -> list[dict[str, Any]]:
    return safe_load_storage(SHARDS[shard_key]["storage"])


def find_driver(driver_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    for shard_key in SHARDS:
        for record in shard_records(shard_key):
            if str(record.get("DriverID")) == str(driver_id):
                return shard_key, record
    return None


def post_driver(shard_key: str, payload: Dict[str, Any]) -> requests.Response:
    return requests.post(f"{SHARDS[shard_key]['url']}/driver", json=payload, timeout=3)


def put_driver(shard_key: str, driver_id: str, payload: Dict[str, Any]) -> requests.Response:
    return requests.put(f"{SHARDS[shard_key]['url']}/driver/{driver_id}", json=payload, timeout=3)


def delete_driver(shard_key: str, driver_id: str) -> requests.Response:
    return requests.delete(f"{SHARDS[shard_key]['url']}/driver/{driver_id}", timeout=3)


@app.route("/", methods=["GET"])
def home():
    return render_template("index.html", shards=SHARDS)


@app.route("/game", methods=["GET"])
def game():
    return render_template("game.html")



@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return ("", 204)


@app.route("/api/overview", methods=["GET"])
def api_overview():
    overview = []
    for shard_key, meta in SHARDS.items():
        records = shard_records(shard_key)
        overview.append(
            {
                "shard_key": shard_key,
                "label": meta["label"],
                "city": meta["city"],
                "url": meta["url"],
                "count": len(records),
                "drivers": records,
            }
        )

    return jsonify({"status": "success", "shards": overview})


@app.route("/api/drivers/<driver_id>", methods=["GET"])
def api_driver_lookup(driver_id: str):
    found = find_driver(driver_id)
    if not found:
        return jsonify({"status": "not_found", "driver_id": driver_id}), 404

    shard_key, record = found
    meta = SHARDS[shard_key]
    return jsonify(
        {
            "status": "found",
            "driver_id": driver_id,
            "shard_key": shard_key,
            "shard_label": meta["label"],
            "city": meta["city"],
            "record": record,
        }
    )


@app.route("/write", methods=["POST"])
def write():
    data = request.get_json(silent=True) or {}
    driver_id = data.get("DriverID")
    city = data.get("City")
    pos_x = data.get("PosX")
    pos_y = data.get("PosY")
    

    if not driver_id or not city:
        print("!!! FAILED: Missing DriverID or City")
        return jsonify(
            {
                "status": "failed",
                "error": "DriverID and City are required",
            }
        ), 400

    target_shard = shard_key_for_city(city)
    if not target_shard:
        print(f"!!! FAILED: No shard for {city}")
        return jsonify(
            {
                "status": "failed",
                "error": "No shard found for city",
                "city": city,
            }
        ), 400

    # Detect current shard (best-effort scan of local JSON files)
    current = find_driver(driver_id)
    current_shard = current[0] if current else None
    current_record = current[1] if current else None

    # Same shard => just insert/update at target + Periodic Cleanup
    if current_shard == target_shard:
        try:
            response = post_driver(target_shard, data)
            
            # Thực hiện dọn dẹp ở các Shard khác để xóa "Dữ liệu mồ côi" 
            # (Hành động này giúp hệ thống tự phục hồi nếu trước đó có Shard bị sập)
            for s_key in SHARDS:
                if s_key != target_shard:
                    try:
                        delete_driver(s_key, driver_id)
                    except:
                        pass # Bỏ qua nếu Shard đó vẫn đang sập

            return jsonify({
                "status": "success",
                "operation": "same_shard_update_with_cleanup",
                "routed_to": SHARDS[target_shard]["label"],
                "result": response.json() if response.text else {}
            })
        except requests.exceptions.RequestException as exc:
            return jsonify({
                "status": "failed",
                "error": "Shard unreachable",
                "message": str(exc)
            }), 503

    # Cross-shard migration: revalidate to target shard.
    # Steps: insert into target first, then delete from old shard.
    if current_shard is None:
        # driver not found anywhere (first sight) => just insert into target
        try:
            response = post_driver(target_shard, data)
        except requests.exceptions.RequestException as exc:
            return jsonify(
                {
                    "status": "failed",
                    "stage": "insert",
                    "error": "Shard unreachable",
                    "message": str(exc),
                }
            ), 503

        if response.status_code not in (200, 201):
            return jsonify(
                {
                    "status": "failed",
                    "stage": "insert",
                    "error": "insert rejected by shard",
                    "http_status": response.status_code,
                    "response": response.text,
                }
            ), 500

        meta = SHARDS[target_shard]
        return jsonify(
            {
                "status": "success",
                "operation": "first_insert",
                "routed_to": meta["label"],
                "city": meta["city"],
                "result": response.json(),
            }
        )

    # current_shard != target_shard
    old_shard = current_shard
    new_shard = target_shard

    # Bước 1: Ghi vào shard mới
    try:
        insert_response = post_driver(new_shard, data)
    except requests.exceptions.RequestException as exc:
        return jsonify({
            "status": "failed",
            "stage": "insert",
            "error": "new shard unavailable",
            "message": str(exc)
        }), 503

    if insert_response.status_code not in (200, 201):
        return jsonify({
            "status": "failed",
            "stage": "insert",
            "error": "insert rejected",
            "http_status": insert_response.status_code
        }), 500

    # Bước 2: Dọn dẹp (Global Cleanup)
    # Thay vì chỉ xóa ở old_shard, ta sẽ quét TẤT CẢ các shard không phải new_shard
    # Điều này giúp xóa bỏ "Dữ liệu mồ côi" nếu trước đó có Shard nào bị sập mà chưa xóa kịp.
    cleanup_reports = []
    for s_key in SHARDS:
        if s_key == new_shard:
            continue
        
        try:
            del_res = delete_driver(s_key, driver_id)
            status = "deleted" if del_res.status_code in (200, 204) else f"error_{del_res.status_code}"
            cleanup_reports.append({"shard": s_key, "status": status})
        except requests.exceptions.RequestException:
            cleanup_reports.append({"shard": s_key, "status": "still_offline"})

    return jsonify({
        "status": "migrated",
        "operation": "global_cleanup_migration",
        "to": SHARDS[new_shard]["label"],
        "cleanup_details": cleanup_reports,
        "insert_result": insert_response.json() if insert_response.text else {}
    })



@app.route("/migrate", methods=["POST"])
def migrate():
    data = request.get_json(silent=True) or {}
    driver_id = data.get("DriverID")
    new_city = data.get("City")
    old_city = data.get("OldCity")

    if not driver_id or not new_city:
        return jsonify(
            {
                "status": "failed",
                "error": "DriverID and City are required",
            }
        ), 400

    new_shard = shard_key_for_city(new_city)
    if not new_shard:
        return jsonify(
            {
                "status": "failed",
                "error": "invalid city",
                "city": new_city,
            }
        ), 400

    source_lookup = None
    if old_city:
        old_shard = shard_key_for_city(old_city)
        if old_shard:
            source_lookup = (old_shard, None)
    else:
        source_lookup = find_driver(driver_id)

    old_shard = source_lookup[0] if source_lookup else None
    source_record = source_lookup[1] if source_lookup and len(source_lookup) > 1 else None

    if old_shard == new_shard:
        try:
            response = put_driver(new_shard, driver_id, data)
        except requests.exceptions.RequestException as exc:
            return jsonify(
                {
                    "status": "failed",
                    "stage": "update",
                    "error": "shard unreachable",
                    "message": str(exc),
                }
            ), 503

        if response.status_code not in (200, 201):
            return jsonify(
                {
                    "status": "failed",
                    "stage": "update",
                    "error": "update rejected by shard",
                    "http_status": response.status_code,
                    "response": response.text,
                }
            ), 500

        return jsonify(
            {
                "status": "migrated",
                "mode": "same_shard_update",
                "from": SHARDS[new_shard]["label"],
                "to": SHARDS[new_shard]["label"],
                "result": response.json(),
            }
        )

    if old_shard is None:
        lookup = find_driver(driver_id)
        if lookup:
            old_shard = lookup[0]
            source_record = lookup[1]

    if old_shard is None:
        return jsonify(
            {
                "status": "failed",
                "error": "source shard not found",
                "hint": "Send OldCity or ensure the driver already exists",
            }
        ), 404

    try:
        insert_response = post_driver(new_shard, data)
    except requests.exceptions.RequestException as exc:
        return jsonify(
            {
                "status": "failed",
                "stage": "insert",
                "error": "new shard unavailable",
                "failed_node": SHARDS[new_shard]["label"],
                "message": str(exc),
            }
        ), 503

    if insert_response.status_code not in (200, 201):
        return jsonify(
            {
                "status": "failed",
                "stage": "insert",
                "error": "insert rejected by shard",
                "failed_node": SHARDS[new_shard]["label"],
                "http_status": insert_response.status_code,
                "response": insert_response.text,
            }
        ), 500

    delete_status = "skipped"
    delete_error = None

    try:
        delete_response = delete_driver(old_shard, driver_id)
        if delete_response.status_code in (200, 204):
            delete_status = "deleted"
        else:
            delete_status = "failed"
            delete_error = delete_response.text
    except requests.exceptions.RequestException as exc:
        delete_status = "failed"
        delete_error = str(exc)

    return jsonify(
        {
            "status": "migrated",
            "mode": "cross_shard_move",
            "from": SHARDS[old_shard]["label"],
            "to": SHARDS[new_shard]["label"],
            "delete_status": delete_status,
            "delete_error": delete_error,
            "insert_result": insert_response.json(),
            "previous_record": source_record,
        }
    )


if __name__ == "__main__":
    print("Running on http://localhost:5000/game")
    app.run(port=5000, debug=False)
