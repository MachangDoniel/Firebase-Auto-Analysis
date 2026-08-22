#!/bin/bash
# Installs the 12:00 AM daily launchd scheduler on macOS

PLIST_NAME="com.neuralsound.dailyanalysis.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="$HOME/Library/LaunchAgents"

mkdir -p "$TARGET_DIR"
cp "$SCRIPT_DIR/$PLIST_NAME" "$TARGET_DIR/"
launchctl unload "$TARGET_DIR/$PLIST_NAME" 2>/dev/null
launchctl load "$TARGET_DIR/$PLIST_NAME"

echo "✅ Scheduler successfully installed! The pipeline will run every day at 12:00 AM."
echo "Log file: $SCRIPT_DIR/daily_analysis.log"
