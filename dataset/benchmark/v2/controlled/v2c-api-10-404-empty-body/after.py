from fastapi import FastAPI, Response

app = FastAPI()
FILES = {}


@app.get("/files/{name}")
def get_file(name: str):
    if name not in FILES:
        return Response(status_code=404)
    return Response(FILES[name])
