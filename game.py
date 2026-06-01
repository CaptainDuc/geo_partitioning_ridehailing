"""Grab-style Geo-Partitioning Game Demo (client-side simulator)

Run:
  python game.py

What it does:
- You control a single character on a 2D map.
- The game sends a "revalidate" update (DriverID, City, Lat, Long)
  periodically to the API Gateway (/write).
- The gateway will automatically migrate the driver between shards.
- The game also polls /api/overview to show which shard currently stores it.

This is a lightweight deliverable to explain the revalidate+migration
workflow visually.
"""

from __future__ import annotations

import json
import math
import random
import threading
import time
from dataclasses import dataclass
from typing import Dict, Tuple

import requests


GATEWAY_BASE = "http://localhost:5000"
DRIVER_ID = "GAME-DRIVER-1"


# Map: left half = Paris (EU-West), right half = London (EU-North)
# We convert map coordinates to fake Lat/Long just for demo.
MAP_W = 100
MAP_H = 60


@dataclass
class Player:
    x: float
    y: float
    speed: float = 2.0


def city_for_position(x: float) -> str:
    return "Paris" if x < MAP_W / 2 else "London"


def latlong_for_position(x: float, y: float) -> Tuple[float, float]:
    # Fake mapping:
    #   Paris shard around ~48.85, 2.35
    #   London shard around ~51.50, -0.12
    if city_for_position(x) == "Paris":
        base_lat, base_lng = 48.85, 2.35
    else:
        base_lat, base_lng = 51.50, -0.12

    # add small offsets
    lat = base_lat + (y - MAP_H / 2) * 0.01
    lng = base_lng + (x - MAP_W / 2) * 0.01
    return lat, lng


def clear_console() -> None:
    # cross-platform-ish
    print("\033[2J\033[H", end="")


def poll_overview_forever(state: Dict[str, object], stop_event: threading.Event) -> None:
    while not stop_event.is_set():
        try:
            r = requests.get(f"{GATEWAY_BASE}/api/overview", timeout=2)
            data = r.json()
            state["overview"] = data
        except Exception as e:
            state["overview_error"] = str(e)
        time.sleep(0.6)


def revalidate_forever(state: Dict[str, object], stop_event: threading.Event, player: Player) -> None:
    while not stop_event.is_set():
        x = int(player.x)
        y = int(player.y)
        city = city_for_position(player.x)

        payload = {
            "DriverID": DRIVER_ID,
            "City": city,
            "PosX": x,
            "PosY": y,
        }

        try:
            res = requests.post(f"{GATEWAY_BASE}/write", json=payload, timeout=3)
            try:
                state["last_write"] = res.json()
            except Exception:
                state["last_write"] = {"http_status": res.status_code, "text": res.text}
        except Exception as e:
            state["last_write_error"] = str(e)

        time.sleep(1.0)  # revalidate interval


def main() -> None:
    # Start threads that: (1) revalidate, (2) poll overview
    player = Player(x=10, y=MAP_H / 2)
    state: Dict[str, object] = {}
    stop_event = threading.Event()

    t_overview = threading.Thread(
        target=poll_overview_forever, args=(state, stop_event), daemon=True
    )
    t_write = threading.Thread(
        target=revalidate_forever, args=(state, stop_event, player), daemon=True
    )

    t_overview.start()
    t_write.start()

    # Simple input loop
    # Controls: W/A/S/D then Enter (because console input is line-based)
    # This is enough for explanation/demonstration.
    while True:
        clear_console()

        city = city_for_position(player.x)
        lat, lng = latlong_for_position(player.x, player.y)

        overview = state.get("overview")
        last_write = state.get("last_write")

        print("=== Geo-Partitioning Game (Grab-style revalidate) ===")
        print(f"DriverID: {DRIVER_ID}")
        print(f"Player position: x={player.x:.1f}, y={player.y:.1f}")
        print(f"Computed City: {city}")
        print(f"Computed Lat/Long: {lat:.4f}, {lng:.4f}")
        print("\n--- Controls ---")
        print("w: up | s: down | a: left | d: right | q: quit")

        # Render a tiny ASCII map
        # mark boundary at half
        boundary = MAP_W // 2
        row = ""
        for xx in range(MAP_W):
            if xx == boundary:
                row += "|"
            elif abs(xx - player.x) < 0.5:
                row += "@"
            else:
                row += "."
        print("\nMap (left=Paris, right=London):")
        print(row)

        if last_write is not None:
            print("\nLast /write response (summary):")
            if isinstance(last_write, dict):
                print(json.dumps(last_write, ensure_ascii=False, indent=2))
            else:
                print(last_write)

        if isinstance(overview, dict):
            print("\nCurrent shard overview (summary):")
            for shard in overview.get("shards", []):
                # show whether our driver exists in this shard
                drivers = shard.get("drivers") or []
                found = any(str(d.get("DriverID")) == DRIVER_ID for d in drivers)
                flag = "YES" if found else "-"
                print(
                    f"  {shard.get('label')} ({shard.get('city')}): count={shard.get('count')} driver_in_shard={flag}"
                )

        if state.get("overview_error"):
            print("\n[Overview polling error]", state["overview_error"])
        if state.get("last_write_error"):
            print("\n[Write error]", state["last_write_error"])

        cmd = input("\nYour move: ").strip().lower()
        if cmd == "q":
            break
        if cmd == "w":
            player.y = max(0, player.y - player.speed)
        elif cmd == "s":
            player.y = min(MAP_H, player.y + player.speed)
        elif cmd == "a":
            player.x = max(0, player.x - player.speed)
        elif cmd == "d":
            player.x = min(MAP_W, player.x + player.speed)

    stop_event.set()
    time.sleep(0.2)


if __name__ == "__main__":
    main()

