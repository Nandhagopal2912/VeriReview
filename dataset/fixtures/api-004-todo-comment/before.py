from flask import jsonify, request

from web.app import app
from web import store


@app.post("/projects")
def create_project():
    project = store.add_project(request.get_json())
    return jsonify(project), 200
