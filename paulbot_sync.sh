#!/bin/bash
set -euo pipefail

# WARNING: This script uses GitHub credentials from an environment file.
# Do NOT use this script in public environments without securing your .env file.
# Be sure to add your .env file to .gitignore!
# Do NOT commit credential files to the repository.
# Consider switching to SSH-based Git instead of embedding credentials in the URL.

# Define paths
REPO_PATH="/etc/paulbot"
DOCKER_IMAGE="paulbot-image"
RUN_SCRIPT="$REPO_PATH/run_paulbot.sh"
ENV_FILE="$REPO_PATH/paulbot.env"

# Files that require an image rebuild
BUILD_FILES=(
    "PaulBot.py"
    "requirements.txt"
    "Dockerfile"
    ".dockerignore"
)

# Files that require container recreation only
RESTART_FILES=(
    "run_paulbot.sh"
)

# Load environment variables
if [[ -f "$ENV_FILE" ]]; then
    export $(grep -v '^#' "$ENV_FILE" | xargs)
else
    echo "Environment file ($ENV_FILE) not found. Exiting."
    exit 1
fi

# Validate GitHub credentials
: "${GITHUB_USERNAME:?GITHUB_USERNAME is not set in $ENV_FILE}"
: "${GITHUB_TOKEN:?GITHUB_TOKEN is not set in $ENV_FILE}"

GITHUB_URL="https://$GITHUB_USERNAME:$GITHUB_TOKEN@github.com/$GITHUB_USERNAME/paulbot.git"

# Navigate to the repository
cd "$REPO_PATH"

# Prevent simultaneous synchronization runs
command -v flock >/dev/null
exec 9>"$(git rev-parse --git-path paulbot-sync.lock)"

if ! flock -n 9; then
    echo "Another PaulBot sync is running. Skipping."
    exit 0
fi

# Track the last successfully deployed commit
DEPLOYED_FILE="$(git rev-parse --git-path paulbot-deployed-head)"

# Refuse to automatically commit unrelated staged changes
if ! git diff --cached --quiet -- . \
    ':(exclude)quotes.json' \
    ':(exclude)stats.json'; then
    echo "ERROR: Unrelated staged changes detected."
    exit 1
fi

# Refuse to deploy uncommitted application changes
if ! git diff --quiet -- "${BUILD_FILES[@]}" "${RESTART_FILES[@]}"; then
    echo "ERROR: Uncommitted deployment file changes detected."
    exit 1
fi

# Identify the current branch and commit
CURRENT_BRANCH="$(git symbolic-ref --short HEAD)"
OLD_HEAD="$(git rev-parse HEAD)"

# Fetch remote changes
echo "Checking for remote repository changes..."
git fetch "$GITHUB_URL" "$CURRENT_BRANCH"

REMOTE_HEAD="$(git rev-parse FETCH_HEAD)"

# Apply remote changes without creating merge commits
if [[ "$OLD_HEAD" != "$REMOTE_HEAD" ]]; then
    git merge --ff-only FETCH_HEAD
else
    echo "Repository is already up-to-date."
fi

CURRENT_HEAD="$(git rev-parse HEAD)"

# Validate the deployment script after synchronization
if [[ ! -f "$RUN_SCRIPT" || ! -x "$RUN_SCRIPT" ]]; then
    echo "ERROR: Run script missing or not executable."
    exit 1
fi

# Determine whether deployment is required
REBUILD=false
RESTART=false
DEPLOYED_HEAD=""

if [[ -f "$DEPLOYED_FILE" ]]; then
    DEPLOYED_HEAD="$(cat "$DEPLOYED_FILE")"
fi

echo "Checking for deployment changes..."

if [[ -z "$DEPLOYED_HEAD" ]] ||
   ! git rev-parse --verify --quiet "${DEPLOYED_HEAD}^{commit}" >/dev/null; then

    echo "No valid deployment baseline found."
    REBUILD=true
    RESTART=true

else

    if ! git diff --quiet "$DEPLOYED_HEAD" "$CURRENT_HEAD" \
        -- "${BUILD_FILES[@]}"; then

        REBUILD=true
        RESTART=true
    fi

    if ! git diff --quiet "$DEPLOYED_HEAD" "$CURRENT_HEAD" \
        -- "${RESTART_FILES[@]}"; then

        RESTART=true
    fi

fi

# Build the replacement image before stopping PaulBot
if [[ "$REBUILD" == true ]]; then
    echo "Building updated Docker image..."
    docker build -t "$DOCKER_IMAGE" .
else
    echo "No image rebuild required."
fi

# Recreate the container if needed
if [[ "$RESTART" == true ]]; then
    echo "Recreating PaulBot container..."
    "$RUN_SCRIPT"
else
    echo "No container recreation required."
fi

# Record deployment only after successful build and recreation
printf '%s\n' "$CURRENT_HEAD" > "$DEPLOYED_FILE"

# Clean up unused images following a successful rebuild
if [[ "$REBUILD" == true ]]; then
    docker image prune -f || echo "Failed to prune unused images."
fi

# Stage persistent application data
echo "Checking for data changes to commit..."
git add -- quotes.json stats.json

# Validate the exact JSON contents staged for commit
if ! python3 - <<'PYTHON'
import json
import subprocess
import sys

files = {
    "quotes.json": list,
    "stats.json": dict,
}

valid = True

for filename, expected_type in files.items():
    try:
        contents = subprocess.check_output(
            ["git", "show", f":{filename}"],
            text=True
        )

        data = json.loads(contents)

        if not isinstance(data, expected_type):
            raise ValueError(
                f"Expected {expected_type.__name__}"
            )

        if not data:
            raise ValueError("Data is unexpectedly empty")

        print(f"Validated {filename}: {len(data)} entries")

    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {filename}: {error}", file=sys.stderr)
        valid = False

sys.exit(0 if valid else 1)
PYTHON
then
    echo "ERROR: Data validation failed. Aborting GitHub sync."
    git restore --staged -- quotes.json stats.json
    exit 1
fi

# Commit validated application data
if ! git diff --cached --quiet; then
    git commit -m "Automated sync at $(date)"
else
    echo "No changes to commit."
fi

# Push new commits, including previously unsuccessful pushes
if [[ "$(git rev-parse HEAD)" != "$REMOTE_HEAD" ]]; then
    echo "Pushing local commits to GitHub..."
    git push "$GITHUB_URL" "HEAD:refs/heads/$CURRENT_BRANCH"
else
    echo "No commits to push."
fi

echo "PaulBot GitHub sync completed successfully."
