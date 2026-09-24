def run(job):
    job.prepare()
    try:
        return job.execute()
    except RuntimeError:
        job.rollback()
        raise
