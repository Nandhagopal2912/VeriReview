import csv
import io

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/import")
def import_csv():
    try:
        rows = list(csv.DictReader(io.StringIO(request.data.decode())))
    except csv.Error:
        return jsonify({"error": "malformed CSV"}), 500
    return jsonify({"rows": len(rows)})
