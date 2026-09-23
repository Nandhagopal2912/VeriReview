from flask import Flask, jsonify

app = Flask(__name__)
TICKETS = {}


class TicketNotFound(Exception):
    pass


@app.errorhandler(TicketNotFound)
def ticket_not_found(error):
    return jsonify({"error": "ticket not found"}), 404


@app.get("/tickets/<int:ticket_id>")
def ticket(ticket_id):
    if ticket_id not in TICKETS:
        raise TicketNotFound()
    return jsonify(TICKETS[ticket_id])
