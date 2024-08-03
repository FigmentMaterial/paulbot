# PaulBot - Quote Generator

PaulBot is a Discord bot that generates and manages quotes, tracks usage statistics, and provides various commands for interacting with quotes and stats. This bot is built using Python and the discord.py library.

## Table of Contents
- [Features](#features)
- [Setup](#setup)
- [Configuration](#configuration)
- [Commands](#commands)
- [Error Handling](#error-handling)
- [Contributing](#contributing)
- [License](#license)

## Features
- Add and manage quotes
- Generate random quotes
- Track command usage statistics
- Track reaction statistics for quotes
- Fetch historical message stats

## Setup

### Prerequisites
- Python 3.7 or higher
- Discord account and a Discord server where you have permission to add bots
- Discord bot token (you can get this from the [Discord Developer Portal](https://discord.com/developers/applications))

### Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/paulbot.git
    cd paulbot
    ```

2. Create and activate a virtual environment (optional but recommended):
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3. Install the required packages:
    ```bash
    pip install -r requirements.txt
    ```

4. Create a `.env` file in the root of the project and add your Discord bot token:
    ```env
    DISCORD_TOKEN=your_discord_token
    ```

### Running the Bot
```bash
python bot.py
Configuration
Intents

Ensure the following intents are enabled in your bot settings on the Discord Developer Portal:

    Message Content Intent
    Server Members Intent (if needed for additional features)

Files

    quotes.json: Stores the list of quotes.
    stats.json: Stores the usage statistics.

Commands

    !test: Test command - displays a test message.
    !addquote <quote>: Add a quote to the list of quotes.
    !paul: Display a random quote from the list of quotes.
    !stats: Display statistics for PaulBot.
    !help: Display the list of available commands.
    !fetch: Scan through messages to update stats.

Error Handling

PaulBot includes error handling for various exceptions and logs errors to paulbot.log. The bot handles:

    File operations (missing files, JSON errors)
    Discord API errors (HTTP exceptions, forbidden actions)
    General exceptions with detailed logging

Contributing

    Fork the repository
    Create a new branch (git checkout -b feature-branch)
    Commit your changes (git commit -m 'Add new feature')
    Push to the branch (git push origin feature-branch)
    Create a new Pull Request

License

This project is licensed under the MIT License - see the LICENSE file for details.


### Explanation

- **Headers**: Used `#`, `##`, `###` to organize sections.
- **Lists**: Used `-` for unordered lists and `1.`, `2.`, `3.` for ordered steps.
- **Code Blocks**: Used triple backticks (\`\`\`) for code blocks, specifying the language (e.g., `bash`, `python`, `env`) for syntax highlighting.
- **Links**: Added links to the Discord Developer Portal and placeholders for the repository and license links.

This README provides a comprehensive guide to your project, covering features, setup instructions, configuration details, available commands, error handling, contributing guidelines, and license information.
