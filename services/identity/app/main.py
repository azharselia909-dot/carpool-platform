from fastapi import FastAPI

app = FastAPI(title="Identity Service")


@app.get("/")
def root():
    return {"service": "identity", "status": "running"}


@app.get("/health")
def health():
    return {"status": "ok"}