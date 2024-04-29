import discord
import random
import json

TOKEN = 'REMOVED_SECRET'

# Define your intents
intents = discord.Intents.default()
intents.messages = True  # Enable message events
intents.message_content = True  # Enable message content

client = discord.Client(intents=intents)

quotes_file = 'quotes.json'  # File to store quotes

# Load existing quotes from file
def load_quotes():
    try:
        with open(quotes_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return []

# Save quotes to file
def save_quotes(quotes):
    with open(quotes_file, 'w') as file:
        json.dump(quotes, file, indent=4)

# Add a new quote
def add_quote(quote):
    quotes.append(quote)
    save_quotes(quotes)

quotes = load_quotes()  # Load existing quotes from file

# Trigger event once bot is connected to Discord to notify server that it is ready
@client.event
async def on_ready():
    print('Logged in as', client.user.name)
    print(client.user.name, ' is ready to receive commands!')

# Trigger events based on commands types in Discord messages
@client.event
async def on_message(message):
        
    if message.author == client.user:
        return  #ignore messages that this generates

    # Convert the message content to lowercase
    content = message.content.lower()

    # Display a test message to make sure the bot and Discord are working together well
    if '!test' in content:
       print("Test message received")
       await message.channel.send("Test command received!")
       
    # Add quotes to the repository
    elif content.startswith('!addquote'):
        print("Adding quote: ", message.content)
        quote = message.content[len('!addquote'):].strip()
        if quote:
            add_quote(quote)
            await message.channel.send('Quote added!')
        else:
            await message.channel.send('Please provide a quote.')

    # Generate and sent a random quote to the Discord channel
    elif '!paul' in content:
        print("Sending random quote...")
        if quotes:
            random_quote = random.choice(quotes)
            await message.channel.send(random_quote)
        else:
            await message.channel.send('No quotes available.')

    # Display a list of available commands to the end user in Discord
    elif '!help' in content:
        # Define the list of available commands and their descriptions
        command_list = [
            ("!test", "Test command - displays a test message."),
            ("!addquote <quote>", "Add a quote to the list of quotes."),
            ("!paul", "Display a random quote from the list of quotes."),
            ("!help", "Display this message.")
        ]

        # Format the list of commands
        formatted_commands = "\n".join(f"- **{command[0]}**: {command[1]}" for command in command_list)

        # Construct the help message
        help_message = (
            "Here are the available commands:\n"
            f"{formatted_commands}"
        )

        # Send the help message to the channel
        await message.channel.send(help_message)

client.run(TOKEN)