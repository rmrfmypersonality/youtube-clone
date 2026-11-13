from fastapi import FastAPI

app = FastAPI(title="YouTube Clone")


@app.get("/health")
def health():
    return {"status": "ok"}