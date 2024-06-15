import discord
import random
import json
import os

TOKEN = 'REMOVED_SECRET'

# Define your intents (Discord security)
intents = discord.Intents.default()
intents.messages = True  # Enable message events
intents.message_content = True  # Enable message content
intents.reactions = True # Enable reaction events

client = discord.Client(intents=intents)

quotes_file = 'quotes.json'  # File to store quotes
stats_file = 'stats.json'   # File to store stats

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
        
# Load existing stats from file
def load_stats():
    try:
        with open(stats_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {"paul_commands": {}, "quote_reaction": {}}
    
# Save stats to file
def save_stats (stats):
    with open(stats_file, 'w') as file:
        json.dump(stats, file, indent=4)

# Add a new quote
def add_quote(quote):
    quotes.append(quote)
    save_quotes(quotes)

quotes = load_quotes()  # Load existing quotes from file
stats = load_stats()    # Load existing stats from file

# Trigger event once bot is connected to Discord to notify server that it is ready
@client.event
async def on_ready():
    print('Logged in as', client.user.name)
    print(client.user.name, ' is ready to receive commands!')

# Fetch previous content for statistics
async def fetch_message_stats(channel):
    async for message in channel.history(limit=None):   # Fetch all messages in the channel
        if message.author == client.user:
            continue    # Ignore messages from PaulBot
        
        content = message.content.lower()
        
        # Process quotes and populate any that were missed
        if content.statswith('!addquote'):
            quote = message.content[len('!addquote'):].strip()
            if quote and quote not in quotes:
                add_quote(quote)
        
        # Track !paul command usage
        if '!paul' in content:
            user_id = str(message.author.id)
            stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
            
        # Track reactions to quotes
        if message.content in quotes:
            stats["quote_reactions"][str(message.id)] = {"content": message.content, "reactions": message.reactions}
            
    save_stats (stats)
    print ("Finished fetching message stats.")
                
# Trigger events based on commands types in Discord messages
@client.event
async def on_message(message):
    print(f"Received message: '{message.content}'")
    print(f"Received message: '{message.author}'")
    print(f"Received message: '{message.channel}'")
    print(f"Received message: '{message.id}'")
        
    if message.author == client.user:
        print("Ignoring message from self!")
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
        user_id = str(message.author.id)
        stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
        save_stats(stats)
        if quotes:
            random_quote = random.choice(quotes)
            await message.channel.send(random_quote)
            stats["quote_reactions"][str(sent_message.id)] = {"content": random_quote, "reactions": 0}
            save_stats(stats)
        else:
            await message.channel.send('No quotes available.')
            
    elif '!stats' in content:
        print("Sending stats...")
        # How many quotes are currently in the quotes.json file
        total_quotes = len(quotes)
        # Who has sent !paul commands the most
        if stats["paul_commands"]:
            top_user_id = max(stats["paul_commands"], key=stats["paul_commands"].get)
            top_user = await client.fetch_user(int(top_user_id))
            most_commands = stats["paul_commands"][top_user_id]
        else:
            top_user = None
            most_commands = 0
        # The quote that has had the most reactions in the channel
        if stats["quote_reaction"]:
            top_quote_id = max(stats["quote_reactions"], key=lambda k: stats["quote_reactions"][k]["reactions"])
            top_quote = stats["quote_reactions"][top_quote_id]["content"]
            most_reactions = stats["quote_reactions"][top_quote_id]["reactions"]
        else:
            top_quote = None
            most_reactions = 0
            
        # Format the stats message
        stats_message = (
            f"**PaulBot Stats:**\n"
            f"**Total Quotes:** {total_quotes}\n"
            f"**Paul's biggest simp:** {top_user} with {most_commands} calls to PaulBot\n"
            f"**Most popular quote:** {top_quote} with {most_reactions} reactions"
        )
        await message.channel.send(stats_message)

    # Fetch message statistics retroactively
    elif '!fetch' in content:
        await fetch_message_stats(message.channel)
        await message.channel.send('Fetch stats from message history.')
        
    # Display a list of available commands to the end user in Discord
    elif '!help' in content:
        # Define the list of available commands and their descriptions
        command_list = [
            ("!test", "Test command - displays a test message."),
            ("!addquote <quote>", "Add a quote to the list of quotes."),
            ("!paul", "Display a random quote from the list of quotes."),
            ("!stats", "Display statistics for PaulBot."),
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

# Collect reaction statistics
@client.event
async def on_reaction_add(reaction, user):
    if user == client.user:
        return      # Ignore reactions that PaulBot generates
    
    message_id = str(reaction.message.id)
    if message_id in stats["quote_reactions"]:
        stats["quote_reactions"][message_id]["reactions"] += 1
        save-stats(stats)
        
# Remove reaction statistics
@client.event
async def on_reaction_remove(reaction, user):
    if user == client.user:
        return      # Ignore reactions that PaulBot generates
    
    message_id = str(reaction.message.id)
    if message_id in stats["quote_reactions"]:
        stats["quote_reactions"][message_id]["reactions"] -= 1
        save_stats (stats)
    

client.run(TOKEN)