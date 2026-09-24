from fastapi import FastAPI

app = FastAPI()
NOTES = {}


@app.get("/notes/{note_id}")
def read_note(note_id: int):
    return NOTES.get(note_id)
