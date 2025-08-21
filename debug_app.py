# debug_app.py
import os
import uvicorn

# ensure "src" is importable
os.environ.setdefault("PYTHONPATH", os.getcwd())

if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host="127.0.0.1",
        port=8000,
        reload=False,   # IMPORTANT: no reloader => single process
        log_level="debug"
    )
