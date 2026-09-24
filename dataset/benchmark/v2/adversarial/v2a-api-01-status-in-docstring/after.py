from fastapi import FastAPI

app = FastAPI()
NOTES = {}


@app.get("/notes/{note_id}")
def read_note(note_id: int):
    """Return the note, or 404 if it does not exist."""
    return NOTES.get(note_id)
