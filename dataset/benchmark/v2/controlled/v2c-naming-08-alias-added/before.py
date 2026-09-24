def retry(outbox):
    tmp_list = [m for m in outbox if m.failed]
    for m in tmp_list:
        m.send()
