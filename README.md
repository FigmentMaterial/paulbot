# PaulBot - Quote Generator and Discord Companion

**PaulBot** is a custom-built Discord bot designed for a private server. It manages a rotating bank of quotes, tracks usage and reactions, and provides a small suite of commands for light automation and entertainment. Built in Python using `discord.py`, it’s backed by simple JSON storage and Docker deployment.

---

![Dockerized](https://img.shields.io/badge/docker-ready-blue)   ![MIT License](https://img.shields.io/badge/license-MIT-green)

---

## Table of Contents

- [Features](#features)
- [Setup](#setup)
  - [Environment](#environment)
  - [Installation](#installation)
  - [Running the Bot](#running-the-bot-docker)
      - [Automating Git Sync](#automating-git-sync-optional)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [File Bind Mounts](#file-bind-mounts)
- [Commands](#commands)
- [File Structure](#file-structure)
  - [Root Directory Layout](#root-directory-layout)
  - [Runtime Files and Version Control](#runtime-files-and-version-control)
- [Logging & Error Handling](#logging--error-handling)
  - [Logging Levels](#logging-levels)
  - [What Gets Logged](#what-gets-logged)
  - [Changing Log Levels](#changing-log-levels)
  - [Log Location](#log-location)
  - [Fallback Behavior](#fallback-behavior)
- [Development & Contribution](#development--contribution)
  - [Local Development](#local-development)
  - [Contributing Code](#contributing-code)
  - [Testing](#testing)
  - [Dependency Maintenance](#dependency-maintenance)
- [Security Disclaimer](#security-disclaimer)
- [License](#license)

---

## Features

- Add, retrieve, and randomly generate Discord quotes
- Track command usage per user
- Log emoji reactions and quote engagement
- Fetch historical messages for analysis
- Persist stats and quotes using JSON files
- Lightweight and Docker-friendly

---

## Setup

### Environment

- **Python:** 3.11 (current Docker runtime; newer Python versions have not been validated)
- **Docker:** used for deployment
- **Linux host:** required for the provided deployment scripts
- **Git:** required to clone the repository and for automated Git sync
- **Python 3 and `flock`:** required on the host for automated Git sync
- **Discord bot token, guild ID and voice channel ID:** configure using the [Discord Developer Portal](https://discord.com/developers/applications) and your server
- **FFmpeg:** installed by the Dockerfile; required separately for local development with voice playback

### Installation

These instructions assume a Linux host and a deployment account with access to Docker and write access to the repository and persistent files. Run commands as that account unless `sudo` is shown. Do not reinitialize an existing installation.

1. Install Docker using the [official installation guide](https://docs.docker.com/get-docker/). Install Git to clone the repository. Install Python 3 and `flock` on the host if using automated sync.

2. For a fresh installation, create the repository directory and clone PaulBot:

    ```bash
    sudo mkdir -p /etc/paulbot
    sudo chown "$(id -u):$(id -g)" /etc/paulbot
    cd /etc/paulbot
    git clone https://github.com/FigmentMaterial/paulbot.git .
    ```

    For an existing installation, use the existing checkout instead.

3. Create the credential file only if it does not already exist:

    ```bash
    cd /etc/paulbot
    if [ ! -e paulbot.env ]; then
        (umask 077; set -C; cat .env.example > paulbot.env)
    fi
    chmod 600 paulbot.env
    nano paulbot.env
    ```

    Populate the Discord token, guild ID, voice channel ID and (if using Git sync) GitHub credentials. The deployment and synchronization account must be able to read `paulbot.env`.

4. Ensure the persistent JSON files exist without overwriting existing data:

    ```bash
    if [ ! -e quotes.json ]; then
        (set -C; printf '[]\n' > quotes.json)
    fi

    if [ ! -e stats.json ]; then
        (set -C; printf '{}\n' > stats.json)
    fi

    chmod 664 quotes.json stats.json
    ```

    **Important:** The repository may already contain populated quote and statistics files. Never initialize them unconditionally. The launch script also initializes missing files, but does not repair existing malformed files. Back up existing data before attempting repairs.

5. Prepare the persistent log directory:

    ```bash
    sudo mkdir -p /var/log/paulbot
    sudo chmod 775 /var/log/paulbot
    ```

    Ensure the deployment account and container can access the paths they need. Adjust ownership or group permissions for your host if necessary.

6. Build the Docker image:

    ```bash
    docker build -t paulbot-image .
    ```

7. Start the bot:

    ```bash
    chmod +x run_paulbot.sh paulbot_sync.sh
    ./run_paulbot.sh
    ```

8. Verify the container and optionally follow the logs:

    ```bash
    docker ps --filter name=paulbot
    docker logs -f paulbot
    ```

    Press Ctrl+C to stop following logs without stopping PaulBot.

### Running the Bot (Docker)

PaulBot runs as a self-contained Docker container with persistent data and logs handled via bind mounts.

Once running, the bot will appear online in Discord and respond to commands like `!paul`. It joins the configured voice channel when listeners are present, reads quotes aloud, and disconnects when the last listener leaves.

From `/etc/paulbot`, launch or recreate the container with:

```bash
./run_paulbot.sh
```

This script:

- Initializes missing quote and statistics files with valid JSON, preserving existing files.
- Checks that the credential file exists, is readable and is nonempty before removing the previous container.
- Mounts the credential file read-only; mounts JSON data and logs read/write.
- Recreates the container using the existing `paulbot-image` image.
- Configures Docker log rotation and the `unless-stopped` restart policy.

To deploy application or dependency changes manually, build first, then recreate the container:

```bash
docker build -t paulbot-image . && ./run_paulbot.sh
```

Building first allows the existing container to continue running if the build fails. Changing only the launch script requires container recreation, not an image rebuild.

#### Automating Git Sync (Optional)

The `paulbot_sync.sh` script fetches updates from GitHub, applies fast-forward changes, deploys updates when necessary, and commits and pushes validated quote and statistics data.

Run it manually from the host:

```bash
cd /etc/paulbot
./paulbot_sync.sh
```

| Changed file | Rebuild image | Recreate container |
|---|:---:|:---:|
| `PaulBot.py` | Yes | Yes |
| `requirements.txt` | Yes | Yes |
| `Dockerfile` | Yes | Yes |
| `.dockerignore` | Yes | Yes |
| `run_paulbot.sh` | No | Yes |
| `paulbot_sync.sh` | No | No |
| `quotes.json`, `stats.json`, `README.md`, `.env.example` | No | No |

Deployment behavior:

- A host-local baseline at `.git/paulbot-deployed-head` records the commit associated with the last successful build and container recreation operation (or a sync requiring neither). It is not committed to GitHub.
- The first run without a valid baseline performs a full deployment. Subsequent runs compare deployment-related files against the recorded commit.
- The image is built before the running container is removed. Failed builds or failed container creation leave the deployment baseline unchanged so the next sync can retry.
- `flock` prevents overlapping runs of the updated synchronization script.
- Divergent Git histories or conflicting local changes require manual reconciliation. The script does not force-push.
- Before committing data, the script validates the staged JSON: `quotes.json` must be a nonempty array and `stats.json` a nonempty object. Invalid or empty data blocks the automatic commit and push. A legitimate data reset requires manual handling.

The JSON guard protects against obvious data loss during automatic commits; it does not detect partial loss, prevent invalid incoming Git changes, or replace backups. The deployment baseline confirms successful deployment commands, not Discord connectivity or full application health. Failure-path and concurrency tests remain deferred.

**Scheduled sync on Hephaestus**

Hephaestus already uses systemd to run synchronization. Use the existing service and timer rather than adding a second scheduler:

```bash
sudo systemctl start paulbot-sync.service
sudo journalctl -u paulbot-sync.service -n 100 --no-pager
systemctl list-timers --all
```

On other hosts without systemd scheduling, an optional hourly cron job may be used instead:

```cron
0 * * * * /etc/paulbot/paulbot_sync.sh >> /var/log/paulbot/sync.log 2>&1
```

The scheduled account needs repository write access, Docker access, readable credentials, and (for cron) permission to write the sync log. Do not configure cron and a systemd timer for the same job.

`paulbot.env` must include `GITHUB_USERNAME` and `GITHUB_TOKEN` for the current authenticated sync workflow. The token must have appropriate access to the repository. If modifying the sync script itself, run the updated script again after it has been pulled; the process that pulled it may still be executing the previous version.

## Configuration

PaulBot relies on both **environment variables** and **bind-mounted files** to function correctly inside its Docker container.

### Environment Variables

These are stored in `/etc/paulbot/paulbot.env`, loaded into the container at runtime. Use the provided `.env.example` file as a reference.

| Variable          | Required | Description |
|-------------------|----------|-------------|
| `DISCORD_TOKEN`   | ✅        | Your Discord bot token from the [Developer Portal](https://discord.com/developers/applications) |
| `DISCORD_GUILD_ID`| ✅        | The ID of your Discord server (guild) |
| `VOICE_CHANNEL_ID`| ✅        | The ID of the voice channel the bot should join |
| `LOG_FILE_PATH`   | ❌        | Optional custom path for logs inside the container (defaults to `/app/logs/paulbot.log`) |
| `LOG_LEVEL`       | ❌        | Logging threshold: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` (defaults to `WARNING`) |
| `GITHUB_USERNAME` | ✅*       | Your GitHub username, used by `paulbot_sync.sh` for sync automation |
| `GITHUB_TOKEN`    | ✅*       | Your GitHub personal access token used for authenticated repo sync |

> ✅* Required only if using `paulbot_sync.sh` to auto-pull, rebuild, and sync with GitHub.

---

### File Bind Mounts

Bind mounts preserve application data and configuration across container rebuilds and removals. `run_paulbot.sh` initializes missing JSON files and checks credentials before replacing the container.

| Host path | Container path | Access | Purpose |
|---|---|---|---|
| `/etc/paulbot/quotes.json` | `/app/quotes.json` | Read/write | Persistent quotes |
| `/etc/paulbot/stats.json` | `/app/stats.json` | Read/write | Persistent statistics |
| `/etc/paulbot/paulbot.env` | `/app/.env` | Read-only | Environment configuration |
| `/var/log/paulbot` | `/app/logs` | Read/write | Persistent application logs |
| `/etc/localtime` | `/etc/localtime` | Read-only | Host local time |
| `/etc/timezone` | `/etc/timezone` | Read-only | Host timezone |

The read-only credential mount prevents writes from inside the container; it does not prevent the application from reading credentials. Keep host file permissions restrictive.

See [Installation](#installation) for host path preparation.

## Commands

PaulBot responds to the following text commands, all prefixed with `!` in Discord:

| Command               | Description                                                                 |
|-----------------------|-----------------------------------------------------------------------------|
| `!paul`               | Responds with a random quote from the database                              |
| `!addquote <text>`    | Adds a new quote to the database                                            |
| `!stats`              | Displays usage statistics and top quote reactions                          |
| `!fetch`              | Scans historical messages (if permissions allow) and updates stats         |
| `!help`               | Displays a list of available commands and descriptions                     |
| `!test`               | Sends a simple response to confirm the bot is online and working           |

Quotes are stored in `quotes.json`, and stats are recorded in `stats.json`.  
Some commands (like `!fetch`) may require elevated permissions, including access to message history.

## File Structure

PaulBot's repository is intentionally lightweight. Credentials and logs stay outside version control. In the public PaulBot repository, the JSON data files are intentionally tracked for synchronization.

### Root Directory Layout

```text
/etc/paulbot/
 ├── PaulBot.py          # Main bot source code
 ├── run_paulbot.sh      # Container launch/recreation script
 ├── paulbot_sync.sh     # Git synchronization and deployment script
 ├── requirements.txt    # Pinned Python dependencies
 ├── Dockerfile          # Docker image configuration
 ├── .dockerignore       # Docker build-context exclusions
 ├── .gitignore          # Git exclusions
 ├── .env.example       # Environment variable template
 ├── paulbot.env        # Host credentials (never commit)
 ├── quotes.json        # Persistent quote data
 ├── stats.json         # Persistent statistics
 └── README.md          # Project documentation
```

The deployment baseline and synchronization lock reside in `.git/`, and application logs reside in `/var/log/paulbot/`.

### Runtime Files and Version Control

Never commit real credential files (`paulbot.env`, `.env`), tokens or runtime logs. Ensure your `.gitignore` and `.dockerignore` exclude credentials and other sensitive local files.

In this public repository, `quotes.json` and `stats.json` are tracked intentionally so the synchronization script can commit and push updates. Their contents and history are publicly accessible. Do not store sensitive or private information in these files while using this workflow. For a deployment that needs private data, use private storage or a private repository and adapt the synchronization script as needed. Adding an already tracked file to `.gitignore` alone does not remove it from version control or history.

## Logging & Error Handling

PaulBot loads its environment configuration before initializing logging. A shared root logging configuration sends records to Docker's console and a rotating application log file. Discord's additional default handler is disabled to avoid duplicate console entries, and Discord and WebSocket loggers inherit the configured threshold unless a child logger overrides it.

### Logging Levels

Set `LOG_LEVEL` in `/etc/paulbot/paulbot.env` to control the logging threshold. The default is `WARNING`; an invalid value falls back to `WARNING` and produces a configuration warning. Values are case-insensitive.

| Level | Intended use |
|---|---|
| `DEBUG` | Temporary detailed troubleshooting, including TTS processing and library diagnostics |
| `INFO` | Startup, recognized commands, voice connections and playback, plus warnings and errors |
| `WARNING` | Default production setting; warnings, errors and critical failures |
| `ERROR` | Errors and critical failures only |
| `CRITICAL` | Critical failures only |

A healthy bot may produce no console output at `WARNING`. Check container health and Discord functionality rather than treating quiet logs as evidence of failure.

### What Gets Logged

- `INFO`: startup and readiness, recognized command names, voice joins and disconnections, and playback status.
- `DEBUG`: quote length, token counts, token processing progress, MP3 generation and reconnect backoff details.
- `WARNING` and above: recoverable problems, configuration issues, connection failures, file I/O errors and application exceptions, as appropriate to severity.

Ordinary Discord messages and the bot's own responses are no longer routinely logged by application code. Command logs record the command name rather than the full message. TTS progress logs omit the actual quote and token text. Exception details and third-party diagnostic logs may still contain sensitive data or message contents, especially at `DEBUG`; this is not comprehensive log sanitization. Review and redact logs before sharing them.

### Changing Log Levels

To temporarily increase verbosity on the Docker host:

```bash
cd /etc/paulbot
nano paulbot.env
```

Set `LOG_LEVEL=INFO` or `LOG_LEVEL=DEBUG`, save the file, and recreate the container:

```bash
./run_paulbot.sh
docker logs --tail 100 paulbot
```

To return to normal operation, set `LOG_LEVEL=WARNING` and run `./run_paulbot.sh` again. Changing `LOG_LEVEL` or `LOG_FILE_PATH` requires a container restart or recreation, not an image rebuild. Recreation is recommended so the current host credential file is mounted even if the editor replaced the file. The Git synchronization script does not automatically redeploy on changes to the untracked `paulbot.env` file.

### Log Location

The two logging destinations have independent rotation policies:

| Destination | Location | Default rotation |
|---|---|---|
| Docker console | `docker logs paulbot` | `50m` per file, up to 3 files |
| Application log | `/app/logs/paulbot.log` in the container; `/var/log/paulbot/paulbot.log` on the host | 10,000,000 bytes per file, 5 backups plus the active file |

Docker's rotation is controlled by the host-side `LOG_MAX_SIZE` and `LOG_MAX_FILE` variables when launching the container. The application file location is configurable through `LOG_FILE_PATH`; its rotation is configured in `PaulBot.py` using `RotatingFileHandler`.

The application log is persistent across container replacements when stored in the mounted `/app/logs` directory. Docker console logs belong to the individual container and are removed when that container is removed. The same application log record appearing once in each destination is intentional.

Ensure the host log directory exists and is writable by the container, as shown in [Installation](#installation).

```bash
docker logs -f paulbot
tail -n 30 /var/log/paulbot/paulbot.log
```

Press Ctrl+C to stop following Docker logs without stopping PaulBot.

### Fallback Behavior

If the configured log file cannot be opened during initialization, PaulBot tries `paulbot.log` in the container's working directory (`/app`). This fallback is not persistent across container replacements. If neither file can be opened, the bot continues with console logging only and emits initialization diagnostics to stderr.

The fallback is designed for initialization failures; it does not guarantee recovery from later disk or rotation failures. Live log rotation and failure-path testing remain deferred.


## Development & Contribution

PaulBot is a personal project designed for a private Discord server, with source code hosted in a public repository. Friends, contributors and curious developers are welcome to explore the code.

### Local Development

Although the bot is designed to run in Docker, you can run it locally for testing. Use Python 3.11 and install FFmpeg separately if testing voice playback. Use a separate test bot, server and data files when possible; do not run a second instance with production credentials.

1. Clone the repository:

    ```bash
    git clone https://github.com/FigmentMaterial/paulbot.git
    cd paulbot
    ```

2. Create a virtual environment and install dependencies:

    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```

3. Add a `.env` file based on `.env.example` and populate the required values.

4. Run the bot directly:

    ```bash
    python3 PaulBot.py
    ```

Logs will still be written to the path defined by `LOG_FILE_PATH`, which should be adjusted accordingly during local testing.

---

### Contributing Code

PaulBot isn’t intended for public use, but contributions or pull requests from friends are welcome. If you want to add features or improve the codebase:

- Fork the repo
- Create a feature branch (`git checkout -b feature/your-feature`)
- Commit your changes with clear messages
- Push and open a pull request

Note: Don’t commit `.env`, `paulbot.env`, token files, personal data, or secrets. Use `.env.example` as a template instead.

---

### Testing

There are no formal automated tests at the moment. Use the following checks after dependency or deployment changes:

```bash
docker ps --filter name=paulbot
docker exec paulbot python -m pip check
docker logs --tail 100 paulbot
```

Verify text commands, quote retrieval, statistics, voice connection, audible TTS playback (including multi-token quotes), voice disconnection and persistent data. The Docker health check is a process check; it does not verify Discord connectivity or audible playback.

When changing deployment scripts, run `bash -n` on both scripts and verify the expected rebuild/recreation behavior. Test invalid-data rejection, failed deployment recovery and concurrent sync handling in an isolated environment, not against live quote and statistics files.

When changing logging, verify that `WARNING` suppresses routine messages, `INFO` shows startup and command activity without duplicates, and `DEBUG` exposes detailed diagnostics. Confirm ordinary messages are not routinely logged, text commands and audible TTS still work, and new records reach the persistent log. Restore `WARNING` after testing. Test forced log rotation and unwritable-path handling separately from the production bot.

### Dependency Maintenance

Keep exact version pins in `requirements.txt` and review dependencies periodically. Update packaging tools in the Dockerfile, rather than modifying a running container.

After changing dependency pins, build and deploy through the normal synchronization workflow (or build and recreate manually). Verify installed packages and compatibility:

```bash
docker exec paulbot python -m pip list
docker exec paulbot python -m pip check
```

Run a Python package security audit in a temporary container using the newly deployed image. The auditor is installed in an isolated virtual environment so its dependencies do not alter the scanned packages:

```bash
docker run --rm --entrypoint sh paulbot-image \
  -c 'python -m venv /tmp/audit &&
      /tmp/audit/bin/pip install --quiet --no-cache-dir pip-audit &&
      /tmp/audit/bin/pip-audit --path /usr/local/lib/python3.11/site-packages'
```

The temporary container is removed on exit. This scans installed Python packages for known vulnerabilities, not system packages or FFmpeg. A successful `pip check` does not imply a clean security audit.

**Maintenance notes (November 25, 2026):**

- `davey==0.1.7` is intentionally pinned because version 0.2.0 caused silent voice playback with `discord.py==2.7.1`. Audible playback was restored and verified after the downgrade. Revisit the pin when a compatible discord.py release is available.
- The final audit reported two remaining PyNaCl 1.5.0 advisories (`PYSEC-2026-1448` and `PYSEC-2026-3002`), both listing 1.6.2 as the fix. Remediation was deferred because discord.py 2.7.1 requires PyNaCl below 1.6. Do not force an incompatible version. Reassess when upstream compatibility changes.
- The Dockerfile pins pip 26.3 and setuptools 84.2.1; neither was flagged in the final audit. The temporary audit environment may still display a notice about its own bundled pip version.


## Security Disclaimer

PaulBot is built for private use among friends and is not intended for public deployment. That said, there are a few important notes:

- **Never commit sensitive data** such as your real `paulbot.env` or `.env` file, Discord tokens, or GitHub credentials.
- The included `.env.example` file should contain placeholders only. Use a narrowly scoped GitHub token. This repository is public; use private storage or a private repository if quotes or statistics need to remain private.
- If you fork or clone this repository:
  - Replace all identifiers (tokens, guild IDs, channel IDs) with your own.
  - Sanitize `quotes.json` and `stats.json` if you plan to share your forked version publicly.
- This bot is not designed for production-scale hosting or public cloud deployment.
- You assume full responsibility for anything the bot does on your server.

> ⚠️ **Reminder:** Discord bots run with elevated privileges on your server. Always keep your tokens secret and scope permissions appropriately.


## License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute PaulBot as long as the original copyright and license notice
are included in any copies or substantial portions of the software.

For full license details, see the [LICENSE](./LICENSE) file in the root of the repository.
