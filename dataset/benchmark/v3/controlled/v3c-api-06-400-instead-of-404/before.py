from flask import Flask, abort, jsonify

app = Flask(__name__)
ARTICLES = {}


@app.get("/articles/<slug>")
def show_article(slug):
    article = ARTICLES.get(slug)
    return jsonify(article)
