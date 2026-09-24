from fastapi import FastAPI, HTTPException

app = FastAPI()
NOTES = {}


@app.get("/notes/{note_id}")
def read_note(note_id: int):
    note = NOTES.get(note_id)
    if note is not None:
        raise HTTPException(status_code=404)
    return note
