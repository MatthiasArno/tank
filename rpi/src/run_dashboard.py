#!/usr/bin/env python3
"""
Starts the FastAPI Dashboard
"""
import sys
import logging
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import uvicorn
import config


def main():
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting dashboard at http://{config.WEB_HOST}:{config.WEB_PORT}")

    # Start Uvicorn
    uvicorn.run(
        "api.dashboard:app",
        host=config.WEB_HOST,
        port=config.WEB_PORT,
        reload=False,
        log_level=config.LOG_LEVEL.lower()
    )


if __name__ == "__main__":
    main()