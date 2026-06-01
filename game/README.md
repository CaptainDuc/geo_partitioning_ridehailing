# Grab-style Geo-Partitioning Game

## What it is

A small console game that simulates a rider/driver moving on a 2D map.

- Left side of map => **Paris** => **EU-West shard**
- Right side of map => **London** => **EU-North shard**

Every second, the game sends a **revalidate** update to:

- `POST http://localhost:5000/write`

Your updated gateway logic will automatically:

- update same-shard records
- or cross-shard migrate (insert new shard first, then delete old shard)

It also polls `GET /api/overview` to show which shard currently contains the driver.

## Run

1. Start gateway + shards (as you already do in your project).
2. Run:
   - `python game.py`
3. Control:
   - `w/a/s/d` then Enter
   - `q` to quit

## Expected demo for lecturer

- Keep moving the player from left (Paris) to right (London).
- The console prints `/write` responses showing `revalidate_cross_shard_move`.
- In the UI, the driver record disappears from one shard and appears in the other.
