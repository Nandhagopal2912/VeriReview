from flask import Flask, jsonify

app = Flask(__name__)
BOOKS = {}


@app.get("/books/<int:book_id>")
def book(book_id):
    if book_id not in BOOKS:
        return jsonify({"error": "book not found"}), 404
    return jsonify(BOOKS[book_id])
