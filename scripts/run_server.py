"""Script to run the Voice Agent FastAPI Tool and Webhook server."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uvicorn
from config.settings import get_settings

if __name__ == "__main__":
    settings = get_settings()
    print(f"🚀 Starting {settings.APP_NAME} on {settings.APP_HOST}:{settings.APP_PORT}...")
    uvicorn.run(
        "src.server.app:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
