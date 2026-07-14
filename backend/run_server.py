"""Entry point for the packaged desktop backend (PyInstaller target).

Not used by `uvicorn app.main:app --reload` local development - that
still works as documented in README.md. This script exists so
PyInstaller has a single importable module to freeze into
"Battery Literature AI Backend.exe", which electron/main.js spawns as a
sidecar process in the packaged app.
"""

import uvicorn

from app.main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
