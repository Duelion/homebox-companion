#!/bin/bash
set -e

# Fix ownership of data directory if running as root
# This handles mounted volumes with incorrect permissions
if [ "$(id -u)" = "0" ]; then
    # Running as root - fix permissions and switch to appuser
    chown -R appuser:appuser /data 2>/dev/null || true
    exec gosu appuser "$@"
else
    # Already running as non-root (appuser)
    exec "$@"
fi
