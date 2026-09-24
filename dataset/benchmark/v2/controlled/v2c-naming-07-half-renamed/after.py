def flush(outbox):
    pending = [m for m in outbox if not m.sent]
    for m in pending:
        m.send()
    return len(tmp_list)
