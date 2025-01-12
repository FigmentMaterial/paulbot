#!/bin/bash

# Define paths
REPO_PATH="/etc/paulbot"
DOCKER_IMAGE="paulbot-image"
DOCKER_CONTAINER="paulbot"
RUN_SCRIPT="/etc/paulbot/run_paulbot.sh"
ENV_FILE="/etc/paulbot/paulbot.env"

# Load environment variables from .env
if [[ -f "$ENV_FILE" ]]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "Environment file ($ENV_FILE) not found. Exiting."
    exit 1
fi

# Validate variables for GitHub authentication
: "${GITHUB_USERNAME:?GITHUB_USERNAME is not set in $ENV_FILE}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set in $ENV_FILE}"

# Authenticate with GitHub
export GITHUB_URL="https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/paulbot.git"

# Validate required files and directories
[[ -f "$RUN_SCRIPT" ]] || { echo "Run script not executable or missing at $RUN_SCRIPT. Exiting."; exit 1; }

# Navigate to the PaulBot repository
cd $REPO_PATH || { echo "Failed to navigate to $REPO_PATH"; exit 1; }

# Check for changes in GitHub repo, then pull if needed
if git fetch --dry-run 2>/dev/null | grep -q .; then
    echo "Changes detected in remote repository. Pulling updates..."
    git pull $GITHUB_URL || { echo "Git pull failed. Exiting."; exit 1; }
else
    echo "Repository is already up-to-date. No pull needed."
fi

# Inspect for changes in core files
echo "Checking for changes in core files..."
if git diff --name-only HEAD~1 | grep -qE "Paulbot.py|requirements.txt"; then
    echo "Changes detected in core files. Restarting Docker container..."

    # Stop and remove the existing container safely
    docker ps -aq --filter "name=$DOCKER_CONTAINER" | xargs -r docker rm -f || echo "No matching container to remove."

    # Rebuild Docker container
    docker build -t $DOCKER_IMAGE . || { echo "Docker build failed. Exiting."; exit 1; }

    # Call script to restart Docker container
    "$RUN_SCRIPT" || { echo "Failed to restart PaulBot. Exiting."; exit 1; }

    # Clean up used Docker images
    docker image prune -f || echo "Failed to prune unused images."
    
else
    echo "No changes detected in core files. Skipping container rebuild."
fi

# Add and commit changes (e.g., updated quotes.json or stats.json)
echo "Checking for changes to commit to GitHub..."
git add quotes.json stats.json || echo "No changes to add."
if ! git diff --cached --quiet; then
    git commit -m "Automated sync at $(date)" || { echo "Failed to commit changes."; exit 1; }
    git push $GITHUB_URL || { echo "Git push failed"; exit 1; }
else
    echo "No changes to commit."
fi

echo "PaulBot GitHub sync completed successfully."