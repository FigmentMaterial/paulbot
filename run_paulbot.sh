#!/bin/bash

# This script runs the PaulBot Docker container.
# Adjust file paths below based on your local environment.
# WARNING: This script mounts an .env file with sensitive crednetials. Do not commit real .env files to the repo!

# Define variables for convenience
IMAGE_NAME="paulbot-image"
CONTAINER_NAME="paulbot"
ENV_FILE="/etc/paulbot/paulbot.env"
QUOTES_FILE="/etc/paulbot/quotes.json"
STATS_FILE="/etc/paulbot/stats.json"
LOG_DIR="/var/log/paulbot"

# Stop and remove existing container (if any)
docker rm -f $CONTAINER_NAME 2>/dev/null || true

# Run the Docker container
docker run -d \
	--restart unless-stopped \
	--name $CONTAINER_NAME \
	-v $ENV_FILE:/app/.env \
	-v $QUOTES_FILE:/app/quotes.json \
	-v $STATS_FILE:/app/stats.json \
	-v $LOG_DIR:/app/logs \
	$IMAGE_NAME