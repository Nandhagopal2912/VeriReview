def flush(outbox):
    tmp_list = [m for m in outbox if not m.sent]
    for m in tmp_list:
        m.send()
    return len(tmp_list)
