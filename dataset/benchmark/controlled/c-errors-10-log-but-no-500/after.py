import logging

from flask import Flask, jsonify

from web.report_engine import build_report

app = Flask(__name__)
logger = logging.getLogger(__name__)


@app.get("/reports/<name>")
def report(name):
    try:
        return jsonify(build_report(name))
    except Exception:
        logger.exception("report %s failed", name)
        return jsonify({"error": "report failed"})
