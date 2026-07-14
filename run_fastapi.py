#!/usr/bin/env python
"""
FastAPI Server Launcher

Run the FastAPI API server on port 8001.

Usage:
    python run_fastapi.py                  # Run with default settings
    python run_fastapi.py --host 0.0.0.0  # Bind to all interfaces
    python run_fastapi.py --reload         # Enable auto-reload for development
"""
import os
import sys


if __name__ == "__main__":
    import uvicorn

    # Default config
    config = {
        "app": "openoutreach.api_v2.main:app",
        "host": "0.0.0.0",
        "port": 8001,
        "reload": "--reload" in sys.argv or "--dev" in sys.argv,
        "log_level": os.environ.get("LOG_LEVEL", "info"),
    }

    # Override host if specified
    if "--host" in sys.argv:
        idx = sys.argv.index("--host")
        if idx + 1 < len(sys.argv):
            config["host"] = sys.argv[idx + 1]

    # Override port if specified
    if "--port" in sys.argv:
        idx = sys.argv.index("--port")
        if idx + 1 < len(sys.argv):
            config["port"] = int(sys.argv[idx + 1])

    print(f"🚀 Starting FastAPI server on {config['host']}:{config['port']}")
    print(f"📖 API docs available at http://localhost:{config['port']}/docs")
    print(f"🔄 Auto-reload: {'enabled' if config['reload'] else 'disabled'}")
    print()

    uvicorn.run(**config)
