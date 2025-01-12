#!/bin/bash

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
	--name $CONTAINER_NAME \
	-v $ENV_FILE:/app/.env \
	-v $QUOTES_FILE:/app/quotes.json \
	-v $STATS_FILE:/app/stats.json \
	-v $LOG_DIR:/app/logs \
	$IMAGE_NAME