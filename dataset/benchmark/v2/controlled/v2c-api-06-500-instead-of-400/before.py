import csv
import io

from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/import")
def import_csv():
    rows = list(csv.DictReader(io.StringIO(request.data.decode())))
    return jsonify({"rows": len(rows)})
