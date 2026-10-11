from flask import Flask, abort, g, jsonify
from werkzeug.exceptions import Forbidden

app = Flask(__name__)
DOCS = {}


@app.get("/docs/<doc_id>")
def read_doc(doc_id):
    doc = DOCS[doc_id]
    if doc["owner"] != g.user:
        raise Forbidden()
    return jsonify(doc)


@app.delete("/docs/<doc_id>")
def delete_doc(doc_id):
    doc = DOCS.pop(doc_id)
    return jsonify({"deleted": doc["title"]})
