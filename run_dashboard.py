#!/usr/bin/env python
# run_dashboard.py
"""
Entry point for running the Dash web application.

Usage:
    python run_dashboard.py

Then navigate to: http://localhost:8050
"""
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('dashboard.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logger.info("Starting Compliance Report Dashboard...")

    from dashboard.app import app

    # Run the app
    app.run(
        debug=True,
        host='0.0.0.0',  # Allow external connections
        port=8050,
        dev_tools_hot_reload=True
    )
