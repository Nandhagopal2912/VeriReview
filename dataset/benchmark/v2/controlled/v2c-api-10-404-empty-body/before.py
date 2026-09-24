from fastapi import FastAPI, Response

app = FastAPI()
FILES = {}


@app.get("/files/{name}")
def get_file(name: str):
    return Response(FILES.get(name, b""))
