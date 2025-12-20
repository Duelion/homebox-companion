#!/bin/bash
# =============================================================================
# Reset Homebox Demo Database
# =============================================================================
# This script:
#   1. Removes the existing Homebox database
#   2. Restarts Homebox service to clear state
#   3. Seeds demo data (user, locations, items)
#
# Called by cron every 30 minutes to prevent demo data from growing too large.
# Note: All active user sessions will be invalidated after reset.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="/data"
DB_FILE="${DATA_DIR}/homebox.db"
LOG_PREFIX="[reset-homebox]"

log() {
    echo "${LOG_PREFIX} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log "Starting demo reset..."

# Remove the database file (Homebox will recreate it)
if [ -f "$DB_FILE" ]; then
    log "Removing existing database..."
    rm -f "${DB_FILE}"*
fi

# Remove any Homebox storage data (uploaded files)
if [ -d "${DATA_DIR}/data" ]; then
    log "Clearing uploaded files..."
    rm -rf "${DATA_DIR}/data"/*
fi

# Signal Homebox to restart via s6
# This ensures Homebox picks up the empty database cleanly
log "Restarting Homebox service..."
if [ -d /run/s6/services/homebox ]; then
    s6-svc -r /run/s6/services/homebox 2>/dev/null || true
fi

# Wait for Homebox to restart and recreate the database
log "Waiting for Homebox to initialize new database..."
sleep 8

# Verify Homebox is responding
for i in $(seq 1 10); do
    if wget -q --spider "http://localhost:7745/api/v1/status" 2>/dev/null; then
        log "Homebox is ready"
        break
    fi
    sleep 1
done

# Run the seed script
log "Seeding demo data..."
"${SCRIPT_DIR}/seed-demo.sh"

log "Demo reset complete! All previous sessions have been invalidated."
