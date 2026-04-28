"""Entry point: python3 run_dashboard.py"""
import sys
import pathlib

# Ensure intraday/ is on the path when run from repo root
sys.path.insert(0, str(pathlib.Path(__file__).parent))

from dashboard.app import app

if __name__ == "__main__":
    print("Starting Market Health Dashboard at http://localhost:8050")
    print("Press Ctrl+C to stop.")
    app.run(host="127.0.0.1", port=8050, debug=False)
