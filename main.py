"""FastAPI root entry point for Vercel, Uvicorn, and ASGI runners."""
from server import app  # noqa: F401

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8010, reload=True)
