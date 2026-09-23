from flask import Flask, jsonify

app = Flask(__name__)
BOOKS = {}


@app.get("/books/<int:book_id>")
def book(book_id):
    return jsonify(BOOKS.get(book_id))
