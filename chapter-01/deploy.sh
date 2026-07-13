#!/usr/bin/env bash
#
# deploy.sh — Beacon v0.1 deployment script
#
# Chapter 1 deployment model:
#   SSH into the production VM, pull the latest code, restart gunicorn.
#
# This is manual, fragile, and has no rollback. It is also the correct
# deployment strategy for a pre-launch internal tool with under 50 users.
# Chapter 7 introduces Docker; Chapter 13 introduces Kubernetes.
#
# Usage:
#   ./deploy.sh
#
# Prerequisites:
#   - SSH key configured for the production host
#   - The production host has the beacon user, directory, and venv set up
#   - gunicorn is configured as a systemd service named 'beacon'

set -euo pipefail

PROD_HOST="${BEACON_HOST:-beacon.example.com}"
PROD_USER="${BEACON_USER:-beacon}"
PROD_DIR="/opt/beacon"

echo "==> Deploying Beacon v0.1 to $PROD_HOST..."

# Step 1: Push the current branch to the production remote.
git push production main

# Step 2: SSH in and run the update sequence.
ssh "$PROD_USER@$PROD_HOST" << 'ENDSSH'
    set -e
    cd /opt/beacon

    echo "==> Pulling latest code..."
    git pull origin main

    echo "==> Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt --quiet

    echo "==> Running migrations..."
    python manage.py migrate --noinput

    echo "==> Collecting static files..."
    python manage.py collectstatic --noinput

    echo "==> Restarting application..."
    sudo systemctl restart beacon

    echo "==> Checking health..."
    sleep 2
    curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/ || echo "WARNING: health check failed"
ENDSSH

echo "==> Deploy complete."
echo "==> Verify: http://$PROD_HOST/"
