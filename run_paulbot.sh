#!/bin/bash
set -euo pipefail

# This script runs the PaulBot Docker container.
# Adjust file paths below based on your local environment.
# WARNING: This script mounts an .env file with sensitive credentials. Do not commit real .env files to the repo!

# Define variables for convenience
IMAGE_NAME="paulbot-image"
CONTAINER_NAME="paulbot"
ENV_FILE="/etc/paulbot/paulbot.env"
QUOTES_FILE="/etc/paulbot/quotes.json"
STATS_FILE="/etc/paulbot/stats.json"
LOG_DIR="/var/log/paulbot"

# Per-container Docker log rotation
LOG_MAX_SIZE="${LOG_MAX_SIZE:-50m}"
LOG_MAX_FILE="${LOG_MAX_FILE:-3}"

# Prep host paths
mkdir -p "$(dirname "$ENV_FILE")" "$(dirname "$QUOTES_FILE")" "$(dirname "$STATS_FILE")" "$LOG_DIR"
touch "$QUOTES_FILE" "$STATS_FILE"

# Stop and remove existing container (if any)
docker rm -f $CONTAINER_NAME 2>/dev/null 2>&1 || true

# Run the Docker container
docker run -d \
	--restart unless-stopped \
	--name $CONTAINER_NAME \
	--log-driver json-file \
	--log-opt "max-size=${LOG_MAX_SIZE}" \
	--log-opt "max-file=${LOG_MAX_FILE}" \
	-v $ENV_FILE:/app/.env \
	-v $QUOTES_FILE:/app/quotes.json \
	-v $STATS_FILE:/app/stats.json \
	-v $LOG_DIR:/app/logs \
	-v /etc/localtime:/etc/localtime:ro \
	-v /etc/timezone:/etc/timezone:ro \
	$IMAGE_NAME