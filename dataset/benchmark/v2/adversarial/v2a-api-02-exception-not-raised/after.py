from fastapi import FastAPI, HTTPException

app = FastAPI()
NOTES = {}


@app.get("/notes/{note_id}")
def read_note(note_id: int):
    if note_id not in NOTES:
        HTTPException(status_code=404, detail="note not found")
    return NOTES.get(note_id)
