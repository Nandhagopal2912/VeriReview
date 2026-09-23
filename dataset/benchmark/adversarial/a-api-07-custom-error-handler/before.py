from flask import Flask, jsonify

app = Flask(__name__)
TICKETS = {}


@app.get("/tickets/<int:ticket_id>")
def ticket(ticket_id):
    return jsonify(TICKETS.get(ticket_id))
