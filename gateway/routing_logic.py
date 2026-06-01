"""Routing Logic for Geo-Partitioned Ride-Hailing (Global Ride-Hailing demo).

Deliverable goal (per assignment):
- Automatically route "Write" requests to the server closest to the driver's city.
- Handle cross-shard migration when a driver moves (e.g., Paris -> London).

This module is intentionally self-contained so it can be presented to the lecturer
as a clear, reusable script.

City mapping used in this repository:
- Paris  -> eu_west
- London -> eu_north

Note: This demo uses HTTP calls to shard services, matching gateway/app.py.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))


SHARDS: Dict[str, Dict[str, str]] = {
    "eu_west": {
        "city": "Paris",
        "label": "EU-West",
        "url": "http://localhost:5001",
    },
    "eu_north": {
        "city": "London",
        "label": "EU-North",
        "url": "http://localhost:5002",
    },
}

CITY_TO_SHARD_KEY = {meta["city"]: key for key, meta in SHARDS.items()}


def shard_key_for_city(city: Optional[str]) -> Optional[str]:
    if not city:
        return None
    return CITY_TO_SHARD_KEY.get(city)


def find_driver_across_shards(driver_id: str) -> Optional[Tuple[str, Dict[str, Any]]]:
    """Best-effort scan across shards (demo only).

    In a real system you'd use an index/metadata service.
    """

    for shard_key in SHARDS:
        url = f"{SHARDS[shard_key]['url']}/_drivers"
        try:
            resp = requests.get(url, timeout=2)
            if resp.status_code != 200:
                continue
            payload = resp.json()
            for record in payload.get("drivers", []):
                if str(record.get("DriverID")) == str(driver_id):
                    return shard_key, record
        except requests.exceptions.RequestException:
            continue

    return None


def post_driver(shard_key: str, payload: Dict[str, Any]) -> requests.Response:
    return requests.post(f"{SHARDS[shard_key]['url']}/driver", json=payload, timeout=3)


def put_driver(shard_key: str, driver_id: str, payload: Dict[str, Any]) -> requests.Response:
    return requests.put(
        f"{SHARDS[shard_key]['url']}/driver/{driver_id}", json=payload, timeout=3
    )


def delete_driver(shard_key: str, driver_id: str) -> requests.Response:
    return requests.delete(f"{SHARDS[shard_key]['url']}/driver/{driver_id}", timeout=3)


def route_write(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Route a Write request based on City."""

    driver_id = payload.get("DriverID")
    city = payload.get("City")

    if not driver_id or not city:
        raise ValueError("DriverID and City are required")

    shard_key = shard_key_for_city(city)
    if not shard_key:
        raise ValueError(f"No shard found for city={city}")

    resp = post_driver(shard_key, payload)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Shard rejected write: {resp.status_code} {resp.text}")

    return {
        "status": "success",
        "operation": "write",
        "routed_to": SHARDS[shard_key]["label"],
        "city": city,
        "driver_id": driver_id,
        "result": resp.json() if resp.text else {},
    }


def route_migrate(driver_id: str, old_city: Optional[str], new_city: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Cross-shard migration for a driver record.

    Algorithm (matching gateway/app.py idea):
    1) Determine new_shard from new_city.
    2) Determine old_shard either from old_city (if provided) or by scanning.
    3) If same shard: update in place.
    4) If cross-shard:
       - insert into new shard
       - delete from old shard
    """

    if not driver_id or not new_city:
        raise ValueError("driver_id and new_city are required")

    new_shard = shard_key_for_city(new_city)
    if not new_shard:
        raise ValueError(f"invalid new_city={new_city}")

    old_shard: Optional[str] = None
    source_record: Optional[Dict[str, Any]] = None

    if old_city:
        old_shard = shard_key_for_city(old_city)

    if old_shard is None:
        found = find_driver_across_shards(driver_id)
        if found:
            old_shard, source_record = found

    if old_shard is None:
        raise RuntimeError("source shard not found (send old_city or ensure driver exists)")

    # Same shard: update
    if old_shard == new_shard:
        resp = put_driver(new_shard, driver_id, payload)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"update rejected: {resp.status_code} {resp.text}")

        return {
            "status": "migrated",
            "mode": "same_shard_update",
            "from": SHARDS[new_shard]["label"],
            "to": SHARDS[new_shard]["label"],
            "driver_id": driver_id,
            "result": resp.json() if resp.text else {},
        }

    # Cross-shard move
    insert_resp = post_driver(new_shard, payload)
    if insert_resp.status_code not in (200, 201):
        raise RuntimeError(
            f"insert rejected by new shard: {insert_resp.status_code} {insert_resp.text}"
        )

    delete_status = "skipped"
    delete_error: Optional[str] = None
    del_resp = delete_driver(old_shard, driver_id)
    if del_resp.status_code in (200, 204):
        delete_status = "deleted"
    else:
        delete_status = "failed"
        delete_error = del_resp.text

    return {
        "status": "migrated",
        "mode": "cross_shard_move",
        "from": SHARDS[old_shard]["label"],
        "to": SHARDS[new_shard]["label"],
        "driver_id": driver_id,
        "delete_status": delete_status,
        "delete_error": delete_error,
        "insert_result": insert_resp.json() if insert_resp.text else {},
        "previous_record": source_record,
    }


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Demo routing logic for geo-partitioning")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_write = sub.add_parser("write", help="Route write by City")
    p_write.add_argument("driver_id")
    p_write.add_argument("city", choices=["Paris", "London"])
    p_write.add_argument("lat", type=float)
    p_write.add_argument("lng", type=float)

    p_mig = sub.add_parser("migrate", help="Migrate driver between shards")
    p_mig.add_argument("driver_id")
    p_mig.add_argument("old_city", choices=["Paris", "London"])
    p_mig.add_argument("new_city", choices=["Paris", "London"])
    p_mig.add_argument("lat", type=float)
    p_mig.add_argument("lng", type=float)

    args = parser.parse_args()

    if args.cmd == "write":
        payload = {
            "DriverID": args.driver_id,
            "City": args.city,
            "Lat": args.lat,
            "Long": args.lng,
        }
        out = route_write(payload)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    if args.cmd == "migrate":
        payload = {
            "DriverID": args.driver_id,
            "City": args.new_city,
            "Lat": args.lat,
            "Long": args.lng,
        }
        out = route_migrate(
            driver_id=args.driver_id,
            old_city=args.old_city,
            new_city=args.new_city,
            payload=payload,
        )
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return


if __name__ == "__main__":
    _cli()

