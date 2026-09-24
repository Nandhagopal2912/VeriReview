from flask import Flask, jsonify

app = Flask(__name__)
NOTES = {}


@app.get("/notes/<int:note_id>")
def read_note(note_id):
    return jsonify(NOTES.get(note_id))
