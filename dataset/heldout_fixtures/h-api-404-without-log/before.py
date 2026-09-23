import logging

from flask import jsonify

from web.app import app
from web.store import get_item

logger = logging.getLogger(__name__)


@app.get("/items/<item_id>")
def item(item_id):
    found = get_item(item_id)
    return jsonify(found), 200
