from flask import Flask, abort, g, jsonify

app = Flask(__name__)
DOCS = {}


@app.get("/docs/<doc_id>")
def read_doc(doc_id):
    doc = DOCS[doc_id]
    return jsonify(doc)


@app.delete("/docs/<doc_id>")
def delete_doc(doc_id):
    if DOCS[doc_id]["owner"] != g.user:
        abort(403)
    doc = DOCS.pop(doc_id)
    return jsonify({"deleted": doc["title"]})
