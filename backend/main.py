from fastapi import FastAPI

app = FastAPI(title="AgingOS Backend")

@app.get("/health")
def health():
    return {"status": "ok"}
