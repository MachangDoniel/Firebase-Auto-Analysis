#!/bin/bash
# Daily execution wrapper for Firebase Analytics & Gemini AI pipeline

# Navigate to the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Run main.py using the virtual environment's python
./venv/bin/python main.py >> daily_analysis.log 2>&1
