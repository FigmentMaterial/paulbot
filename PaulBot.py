from pickle import NONE
import discord
import random
import json

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
    except (FileNotFoundError, json.JSONDecodeError):
        stats = {
            "paul_commands": {},
            "quote_reactions": {},
        }
        # Initialize required keys if they don't exist
        stats.setdefault('paul_commands', {})
        stats.setdefault('quote_reactions', {})
        return stats
    
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
    if stats.get("fetch_completed", False) == True:
        await channel.send("Fetch already completed. Skipping fetch.")
        return
        
    async for message in channel.history(limit=None):   # Fetch all messages in the channel after the last fetch command
        content = message.content.lower()
               
        # Track !paul command usage
        if message.author != client.user and '!paul' in content:
            user_id = str(message.author.id)
            stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
            save_stats(stats)   # Save updated stats here
            continue    #Skip further processing for non-PaulBot messages
            
        # Track reactions to quotes
        if message.author == client.user:
            for quote in quotes:
                if quote.lower() in content:
                    # Check if the message has reactions
                    reactions_count = sum(reaction.count for reaction in message.reactions)
                    if reactions_count > 0:
                        # Aggregate reactions for each occurrence of the quote
                        if quote in stats["quote_reactions"]:
                            stats["quote_reactions"][quote]["reactions"] += reactions_count
                        else:
                            stats["quote_reactions"][quote] = {"content": quote, "reactions": reactions_count}
                        save_stats(stats)  # Save updated stats here
    # Set the fetch_completed flag to True after processing
    stats["fetch_completed"] = True
    save_stats(stats)   # Save updated stats here
    # Post confirmation to channel
    await channel.send('Fetched stats from message history.')
                
# Trigger events based on commands types in Discord messages
@client.event
async def on_message(message):
    print(f"Received message: '{message.content}'")
    print(f"Received message: '{message.author}'")
    print(f"Received message: '{message.channel}'")
    print(f"Received message: '{message.id}'")
        
    if message.author == client.user:
        return  #ignore messages that this generates

    # Convert the message content to lowercase for processing
    content = message.content.lower()

    # Display a test message to make sure the bot and Discord are working together well
    if '!test' in content:
       print("Test message received")
       await message.channel.send("Test command received!")
       
    # Add quotes to the repository
    elif content.startswith('!addquote'):
        quote = message.content[len('!addquote'):].strip()
        if quote:
            add_quote(quote)
            await message.channel.send('Quote added!')
        else:
            await message.channel.send('Please provide a quote.')

    # Generate and sent a random quote to the Discord channel
    elif '!paul' in content:
        user_id = str(message.author.id)
        stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
        save_stats(stats)   # Save updated stats here
        
        if quotes:
            random_quote = random.choice(quotes)
            sent_message = await message.channel.send(random_quote)
        else:
            await message.channel.send('No quotes available.')
            
    elif '!stats' in content:
        # How many quotes are currently in the quotes.json file
        total_quotes = len(quotes)
        # Who has sent !paul commands the most
        if stats["paul_commands"]:
            top_user_id = max(stats["paul_commands"], key=stats["paul_commands"].get)
            top_user = await client.fetch_user(int(top_user_id))
            most_commands = stats["paul_commands"][top_user_id]
            top_user_mention = f"<@{top_user_id}>"  #format the mention
        else:
            top_user = None
            most_commands = 0
            top_user_mention = "None"
        # The quote that has had the most reactions in the channel
        if stats["quote_reactions"]:
            top_quote_id = max(stats["quote_reactions"], key=lambda k: stats["quote_reactions"][k]["reactions"])
            top_quote = stats["quote_reactions"][top_quote_id]["content"]
            most_reactions = stats["quote_reactions"][top_quote_id]["reactions"]
        else:
            top_quote = None
            most_reactions = 0
            
        # Format the stats message
        # Create an Embed instance    
        embed = discord.Embed(title="PaulBot Statistics", color=0x7289DA)    
        # Add fields for each statistic
        embed.add_field(name="Total Quotes", value=total_quotes, inline=False)
        embed.add_field(name="Paul's Biggest Simp", value=f"{top_user_mention} with {most_commands} calls to PaulBot", inline=False)
        embed.add_field(name="Most Popular Quote", value=f"With {most_reactions}\n{top_quote}", inline=False)
        await message.channel.send(embed)

    # Fetch message statistics retroactively
    elif '!fetch' in content:
        await fetch_message_stats(message.channel)
        
    # Display a list of available commands to the end user in Discord
    elif '!help' in content:
        # Define the list of available commands and their descriptions
        command_list = [
            ("!test", "Test command - displays a test message."),
            ("!addquote <quote>", "Add a quote to the list of quotes."),
            ("!paul", "Display a random quote from the list of quotes."),
            ("!stats", "Display statistics for PaulBot."),
            ("!help", "Display this message."),
            ("!fetch", "Scan through messages to update stats.")
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
    
    message = reaction.message
    content = message.content.lower()
    
    if message.author == client.user:
        for quote in quotes:
            if quote.lower() in content:
                if quote in stats["quote_reactions"]:
                    stats["quote_reactions"][quote]["reactions"] += 1
                else:
                    stats["quote_reactions"][quote] = {"content": quote, "reactions": 1}
                save_stats(stats) # Save stats here
                break   # Stop checking quotes once a match is found
        
# Remove reaction statistics
@client.event
async def on_reaction_remove(reaction, user):
    if user == client.user:
        return      # Ignore reactions that PaulBot generates
    
    message = reaction.message
    content = message.content.lower()
    
    if message.author == client.user:
        for quote in quotes:
            if quote.lower() in content:
                if quote in stats["quote_reactions"] and stats["quote_reactions"][quote]["reactions"] > 0:
                    stats["quote_reactions"][quote]["reactions"] -= 1
                    if stats["quote_reactions"][quote]["reactions"] == 0:
                        del stats["quote_reactions"][quote]
                    save_stats(stats)   #Save stats here
                break   # Stop checking quotes once a match is found

client.run(TOKEN)