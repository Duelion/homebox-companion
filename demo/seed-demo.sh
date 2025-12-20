#!/bin/bash
# =============================================================================
# Seed Demo Data
# =============================================================================
# Creates the demo user and populates initial locations/items.
# Called on container startup and after each reset.
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_PREFIX="[seed-demo]"

log() {
    echo "${LOG_PREFIX} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# Wait for Homebox API to be ready
wait_for_homebox() {
    log "Waiting for Homebox API to be ready..."
    for i in $(seq 1 30); do
        if wget -q --spider "http://localhost:7745/api/v1/status" 2>/dev/null; then
            log "Homebox API is ready!"
            return 0
        fi
        sleep 1
    done
    log "ERROR: Homebox API did not become ready in time"
    return 1
}

wait_for_homebox

# Run the Python seed script
log "Running Python seed script..."
cd /app
/app/.venv/bin/python -m demo.seed_demo

log "Demo seeding complete!"
