from flask import Flask, request, jsonify
import json
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE = os.path.join(BASE_DIR, "storage.json")

# tạo file nếu chưa có
if not os.path.exists(FILE):
    with open(FILE, "w") as f:
        json.dump([], f)


@app.route("/driver", methods=["POST"])
def add_driver():
    data = request.json
    driver_id = data.get("DriverID")

    with open(FILE, "r") as f:
        db = json.load(f)

    # Upsert logic: check if driver already exists
    updated = False
    for index, record in enumerate(db):
        if str(record.get("DriverID")) == str(driver_id):
            db[index] = data
            updated = True
            break
    
    if not updated:
        db.append(data)

    with open(FILE, "w") as f:
        json.dump(db, f)

    return jsonify({"status": "stored in EU-West", "operation": "upsert", "updated": updated})


@app.route("/driver/<driver_id>", methods=["PUT"])
def update_driver(driver_id):
    data = request.json

    with open(FILE, "r") as f:
        db = json.load(f)

    updated = False
    for index, record in enumerate(db):
        if str(record.get("DriverID")) == str(driver_id):
            db[index] = data
            updated = True
            break

    if not updated:
        db.append(data)

    with open(FILE, "w") as f:
        json.dump(db, f)

    return jsonify({"status": "updated", "created": not updated})


@app.route("/driver/<driver_id>", methods=["DELETE"])
def delete_driver(driver_id):
    with open(FILE, "r") as f:
        db = json.load(f)

    db = [d for d in db if d.get("DriverID") != driver_id]

    with open(FILE, "w") as f:
        json.dump(db, f)

    return jsonify({"status": "deleted"})


if __name__ == "__main__":
    app.run(port=5001)

