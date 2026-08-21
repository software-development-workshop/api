from fastapi import FastAPI

app = FastAPI(title="UdeSA-X Accounts")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
