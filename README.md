# PaulBot - Quote Generator and Discord Companion

**PaulBot** is a custom-built Discord bot designed for a private server. It manages a rotating bank of quotes, tracks usage and reactions, and provides a small suite of commands for light automation and entertainment. Built in Python using `discord.py`, it’s backed by simple JSON storage and Docker deployment.

---

![Dockerized](https://img.shields.io/badge/docker-ready-blue)   ![MIT License](https://img.shields.io/badge/license-MIT-green)

---

## 📄 Table of Contents

- [Features](#features)
- [Setup](#setup)
  - [Environment](#environment)
  - [Installation](#installation)
  - [Running the Bot](#running-the-bot)
      - [Automating Git Sync](#automating-git-sync)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [File Bind Mounts](#file-bind-mounts)
- [Commands](#commands)
- [Logging & Error Handling](#logging--error-handling)
- [Development & Contribution](#development--contribution)
- [Security Disclaimer](#security-disclaimer)
- [License](#license)

---

## ✨ Features

- Add, retrieve, and randomly generate Discord quotes
- Track command usage per user
- Log emoji reactions and quote engagement
- Fetch historical messages for analysis
- Persist stats and quotes using JSON files
- Lightweight and Docker-friendly

---

## ⚙️ Setup

### 🧪 Environment

- **Python:** 3.11+ recommended
- **Docker:** used for deployment
- **Linux host:** required
- **Discord bot token** and **guild ID** from [Discord Developer Portal](https://discord.com/developers/applications)

### 📦 Installation

1. Install Docker (Linux/macOS/Windows):

    Follow the official Docker installation guide for your platform:
    [https://docs.docker.com/get-docker](https://docs.docker.com/get-docker)

2. Clone the PaulBot repository to /etc/paulbot:

    ```bash
    sudo mkdir /etc/paulbot/
    cd /etc/paulbot
    git clone https://github.com/FigmentMaterial/paulbot.git .
    ```

3. Create a `.env` file based on the provided `.env.example` template:

    ```bash
    cp .env.example /etc/paulbot/paulbot.env
    ```

4. Edit `.env` with your Discord bot token, guild ID, voice channel ID, and GitHub credentials:

    ```bash
    nano /etc/paulbot/paulbot.env
    ```
5. Ensure `quotes.json` and `stats.json` exist in `/etc/paulbot/`:

    ```bash
    echo "[]" | sudo tee /etc/paulbot/quotes.json
    echo "{}" | sudo tee /etc/paulbot/stats.json
    sudo chmod 664 /etc/paulbot/*.json
    ```
6. Ensure logs directory exists in `/var/log/paulbot`:

    ```bash
    sudo mkdir -p /var/log/paulbot
    sudo chmod 775 /var/log/paulbot
    ```

7. Build the Docker image:

    ```bash
    docker build -t paulbot-image .
    ```

8. Run the bot using the provided launch script:

    ```bash
    chmod +x run_paulbot.sh
    ./run_paulbot.sh
    ```

9. (Optional) View runtime logs:

    ```bash
    docker logs -f paulbot
    ```


### 🐳 Running the Bot (Docker)

PaulBot is designed to run as a self-contained Docker container with persistent data and logs handled via bind mounts.

✔️ Once running, the bot will appear online in your Discord server and respond to commands like `!paul`. It will also idle in a voice channel that you configure and verbally spew random quotes on a 60-second interval.

Once installed, you can launch the bot with:

```bash
./run_paulbot.sh
```
This script will:
- Stop and remove any previously running paulbot container
- Mount your environment file, JSON data, and logs into the container
- Start a new container using the latest paulbot-image

To follow runtime logs:
```bash
docker logs -f paulbot
```

💡 If you make changes to the source code, be sure to rebuild the image:
```bash
docker build -t paulbot-image .
```

#### 🔄 Automating Git Sync (Optional)

The optional `paulbot_sync.sh` script can:

- Pull the latest changes from GitHub
- Rebuild the Docker image if core files changed
- Restart the container if needed
- Commit and push updates to quotes or stats (if applicable)

To run this regularly, you can set up a cron job:
```bash
crontab -e
```

Add the following line to sync every hour:
```bash
0 * * * * /etc/paulbot/paulbot_sync.sh >> /var/log/paulbot/sync.log 2>&1
```

Make sure `paulbot_sync.sh` is executable:
```bash
chmod +x /etc/paulbot/paulbot_sync.sh
```

⚠️ Your `.env` file must include GITHUB_USERNAME and GITHUB_TOKEN for sync to work properly.


## 🛠️ Configuration

PaulBot relies on both **environment variables** and **bind-mounted files** to function correctly inside its Docker container.

### 🔐 Environment Variables

These are stored in `/etc/paulbot/paulbot.env`, loaded into the container at runtime. Use the provided `.env.example` file as a reference.

| Variable          | Required | Description |
|-------------------|----------|-------------|
| `DISCORD_TOKEN`   | ✅        | Your Discord bot token from the [Developer Portal](https://discord.com/developers/applications) |
| `DISCORD_GUILD_ID`| ✅        | The ID of your Discord server (guild) |
| `VOICE_CHANNEL_ID`| ✅        | The ID of the voice channel the bot should join |
| `LOG_FILE_PATH`   | ❌        | Optional custom path for logs inside the container (defaults to `/app/logs/paulbot.log`) |
| `GITHUB_USERNAME` | ✅*       | Your GitHub username, used by `paulbot_sync.sh` for sync automation |
| `GITHUB_TOKEN`    | ✅*       | Your GitHub personal access token used for authenticated repo sync |

> ✅* Required only if using `paulbot_sync.sh` to auto-pull, rebuild, and sync with GitHub.

---

### 📁 File Bind Mounts

The Docker container uses file bind mounts to ensure that important data — like quotes, stats, logs, and environment variables — is stored outside the container.  
This makes the data **persistent across container rebuilds or removals**, preserving state and configuration reliably.

These files must be present on the host and are mounted into the container by the `run_paulbot.sh` launch script.

| Host Path                   | Container Path     | Description                      |
|----------------------------|--------------------|----------------------------------|
| `/etc/paulbot/quotes.json` | `/app/quotes.json` | Persistent storage of quotes     |
| `/etc/paulbot/stats.json`  | `/app/stats.json`  | Persistent usage statistics      |
| `/etc/paulbot/paulbot.env` | `/app/.env`        | Environment configuration        |
| `/var/log/paulbot`         | `/app/logs`        | Directory for application logs   |

Ensure all files and the log directory have the correct permissions, as shown in the [Installation](#installation) section.

## 💬 Commands

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

## 🗂️ File Structure

PaulBot’s repository is intentionally lightweight. Most files serve either runtime logic, configuration, or persistent data handling. Sensitive and persistent files are **bind-mounted** and excluded from version control.

### 📁 Root Directory Layout
```
/etc/paulbot/ 
 ├── PaulBot.py         # Main bot source code
 ├── run_paulbot.sh     # Launch script for building/running the Docker container
 ├── paulbot_sync.sh    # (Optional) Sync script for git pull + container restart
 ├── requirements.txt   # Python dependencies for discord.py and logging
 ├── Dockerfile         # Docker image configuration
 ├── .env.example       # Template file for environment variables
 ├── quotes.json        # Stores saved quotes (mounted at runtime)
 ├── stats.json         # Tracks command/reaction stats (mounted at runtime)
 └── README.md          # Project documentation
 ```

### 🛑 Ignored at Runtime

These files are expected to exist at runtime but **should not be committed**:

- `.env` → Contains sensitive credentials (token, GitHub auth)
- `quotes.json` → User-generated content
- `stats.json` → Dynamic usage data
- Log files in `/var/log/paulbot/` → App output and diagnostics

All of the above are excluded via `.gitignore`, and most are created during [Installation](#installation).

**Note:** In this repository, `quotes.json` and `stats.json` are _not_ excluded by default.  
This is intentional to allow sharing data with a specific friend group.  
If you're running your own fork or a public-facing version, you **should exclude these files** to protect user privacy and reduce potential repo clutter.


## 🧾 Logging & Error Handling

PaulBot logs useful information for debugging, monitoring, and post-mortem analysis. Logs are written to a persistent bind-mounted location inside the container (default: `/app/logs/paulbot.log`).

### 📝 What Gets Logged

- Bot startup and shutdown events
- Commands executed by users
- Reactions and statistics tracking
- File I/O issues (missing or corrupt JSON)
- Discord API errors (e.g., permission issues)
- Any uncaught exceptions or fatal crashes

### 🔧 Log Location

The location is configurable using the `LOG_FILE_PATH` environment variable. If not specified, it defaults to:
`/app/logs/paulbot.log`

This path is bind-mounted from the host machine, typically:
`/var/log/paulbot/`

Ensure this directory exists on the host and is writable by the container, as shown in the [Installation](#installation) section.

### ❌ Fallback Behavior

If the log path is invalid or unwritable, the bot falls back to writing logs to `paulbot.log` in the container's current working directory. This fallback is **not persistent** and will be lost when the container is removed.

Tip: Use `docker logs -f paulbot` to tail logs directly if needed.


## 👩‍💻 Development & Contribution

PaulBot is a private, personal project — but if you’re a friend, contributor, or curious developer, feel free to poke around.

### 🧱 Local Development

Although the bot is designed to run in Docker, you can run it locally for testing:

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

### 🛠️ Contributing Code

PaulBot isn’t intended for public use, but contributions or pull requests from friends are welcome. If you want to add features or improve the codebase:

- Fork the repo
- Create a feature branch (`git checkout -b feature/your-feature`)
- Commit your changes with clear messages
- Push and open a pull request

Note: Don’t commit `.env`, token files, personal data, or secrets. Use `.env.example` as a template instead.

---

### 🧪 Testing

There are no formal tests at the moment. You break it, you fix it. 😎


## 🔐 Security Disclaimer

PaulBot is built for private use among friends and is not intended for public deployment. That said, there are a few important notes:

- **Never commit sensitive data** such as your real `.env` file, Discord tokens, or GitHub credentials.
- The included `.env.example` file is safe for sharing and should be used as a template only.
- If you fork or clone this repository:
  - Replace all identifiers (tokens, guild IDs, channel IDs) with your own.
  - Sanitize `quotes.json` and `stats.json` if you plan to share your forked version publicly.
- This bot is not designed for production-scale hosting or public cloud deployment.
- You assume full responsibility for anything the bot does on your server.

> ⚠️ **Reminder:** Discord bots run with elevated privileges on your server. Always keep your tokens secret and scope permissions appropriately.


## 📜 License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute PaulBot as long as the original copyright and license notice
are included in any copies or substantial portions of the software.

For full license details, see the [LICENSE](./LICENSE) file in the root of the repository.
