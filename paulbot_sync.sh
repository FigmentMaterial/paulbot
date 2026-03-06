#!/bin/bash

# WARNING: This script uses GitHub credentials from an environment file.
# Do NOT use this script in public environments without securing your .env file.
# Be sure to add your .env file to .gitignore!
# Consider switching to SSH-based Git instead of embedding credentials in the URL.

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
cd "$REPO_PATH" || { echo "Failed to navigate to $REPO_PATH"; exit 1; }

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
OLD_HEAD="$(git rev-parse HEAD)"

# Fetch the current branch from the authenticated GitHub URL
git fetch "$GITHUB_URL" "$CURRENT_BRANCH" || { echo "Git fetch failed. Exiting."; exit 1; }

REMOTE_HEAD="$(git rev-parse FETCH_HEAD)"

# Pull only if remote HEAD differs from local HEAD
if [[ "$OLD_HEAD" != "$REMOTE_HEAD" ]]; then
    echo "Changes detected in remote repository. Pulling updates..."
    git pull --ff-only "$GITHUB_URL" "$CURRENT_BRANCH" || { echo "Git pull failed. Exiting."; exit 1; }
    NEW_HEAD="$(git rev-parse HEAD)"
else
    echo "Repository is already up-to-date. No pull needed."
    NEW_HEAD="$OLD_HEAD"
fi

# Inspect pulled changes for core files
echo "Checking for changes in core files..."
if [[ "$OLD_HEAD" != "$NEW_HEAD" ]] && git diff --name-only "$OLD_HEAD" "$NEW_HEAD" | grep -qE '(^|/)(Paulbot\.py|requirements\.txt)$'; then
    echo "Changes detected in core files. Restarting Docker container..."

    docker ps -aq --filter "name=$DOCKER_CONTAINER" | xargs -r docker rm -f || echo "No matching container to remove."
    docker build -t "$DOCKER_IMAGE" . || { echo "Docker build failed. Exiting."; exit 1; }
    "$RUN_SCRIPT" || { echo "Failed to restart PaulBot. Exiting."; exit 1; }
    docker image prune -f || echo "Failed to prune unused images."
else
    echo "No changes detected in core files. Skipping container rebuild."
fi

# Add and commit changes (e.g., updated quotes.json or stats.json)
echo "Checking for changes to commit to GitHub..."
git add quotes.json stats.json || echo "No changes to add."
if ! git diff --cached --quiet; then
    git commit -m "Automated sync at $(date)" || { echo "Failed to commit changes."; exit 1; }
    git push "$GITHUB_URL" || { echo "Git push failed"; exit 1; }
else
    echo "No changes to commit."
fi

echo "PaulBot GitHub sync completed successfully."