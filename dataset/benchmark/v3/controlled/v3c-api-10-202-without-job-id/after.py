from flask import Flask, jsonify

app = Flask(__name__)
QUEUE = []


@app.post("/exports")
def start_export():
    job_id = len(QUEUE) + 1
    QUEUE.append(job_id)
    return jsonify({"status": "queued"}), 202
