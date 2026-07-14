"""Entry point for the PyInstaller-frozen desktop sidecar binary.

`uvicorn main:app` (the CLI) resolves "main:app" by importing the module
by name, which PyInstaller's static analysis can't follow -- it only sees
whatever this script imports directly. So the frozen binary calls
uvicorn.run() with the already-imported `app` object instead of the CLI.

Not used by any other entry point (dev/Docker keep using `uvicorn
main:app --reload`/gunicorn) -- see desktop-app/README.md.
"""

import uvicorn

from main import app

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
