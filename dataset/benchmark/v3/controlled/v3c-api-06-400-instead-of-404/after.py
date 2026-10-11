from flask import Flask, abort, jsonify

app = Flask(__name__)
ARTICLES = {}


@app.get("/articles/<slug>")
def show_article(slug):
    article = ARTICLES.get(slug)
    if article is None:
        abort(400)
    return jsonify(article)
