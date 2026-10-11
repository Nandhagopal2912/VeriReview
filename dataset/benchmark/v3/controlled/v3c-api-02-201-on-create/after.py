from flask import Flask, jsonify, request

app = Flask(__name__)
NOTES = []


@app.post("/notes")
def create_note():
    note = {"id": len(NOTES) + 1, "text": request.json["text"]}
    NOTES.append(note)
    return jsonify(note), 201
