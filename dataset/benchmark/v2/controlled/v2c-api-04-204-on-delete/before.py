from flask import Flask, jsonify

app = Flask(__name__)
TASKS = {}


@app.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    TASKS.pop(task_id, None)
    return jsonify({"deleted": task_id})
