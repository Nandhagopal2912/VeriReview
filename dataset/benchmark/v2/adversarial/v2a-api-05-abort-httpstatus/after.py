from http import HTTPStatus

from flask import Flask, abort, jsonify

app = Flask(__name__)
NOTES = {}


@app.get("/notes/<int:note_id>")
def read_note(note_id):
    if note_id not in NOTES:
        abort(HTTPStatus.NOT_FOUND)
    return jsonify(NOTES[note_id])
