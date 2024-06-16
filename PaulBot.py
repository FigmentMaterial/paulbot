from ast import Try
from symbol import try_stmt
import discord
import random
import json
from discord.enums import try_enum
from dotenv import load_dotenv
import os
import logging
from logging.handlers import RotatingFileHandler

# Setup a logging function to process error handling throughout the script
def setup_logging():
    # Configure logging to a file
    logging.basicConfig(
       filename='paulbot.log',
        format='%(asctime)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )

    # Configure a rotating file handler to keep logs from growing too large
    handler = RotatingFileHandler('paulbot.log', maxBytes=1024*1024, backupCount=5)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logging.getLogger('').addHandler(handler)

# Initialize logging
setup_logging()    

# Load environment variables for Discord token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Check if the token is loaded correctly
if TOKEN is None:
    logging.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
    raise ValueError("No Discord token found. Please set the DISCORD_TOKEN environment variable.")

# Define your intents (Discord security)
intents = discord.Intents.none()
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
        logging.warning(f"FileNotFoundError: Quotes file '{quotes_file}' not found.")
        return []
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: Failed to decode JSON in '{quotes_file}'. Error: {e}. Validate that file is not empty and is formatted in JSON.")
        return []
    except Exception as e:
        logging.error(f"Unexpected error loading quotes from '{quotes_file}'. Error: {e}.")
        return []

# Save quotes to file
def save_quotes(quotes):
    try:
        with open(quotes_file, 'w') as file:
            json.dump(quotes, file, indent=4)
    except OSError as e:
        logging.error(f"OSError: Failed to save quotes to '{quotes_file}'. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexcepted error saving quotes to '{quotes_file}'. Error: {e}.")
        
# Load existing stats from file
def load_stats():
    try:
        with open(stats_file, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        logging.warning(f"FileNotFoundError: Stats file '{stats_file}' not found.")
        return {"paul_commands": {}, "quote_reactions": {}}
    except json.JSONDecodeError as e:
        logging.warning(f"JSONDecodeError: Failed to decode JSON in '{stats_file}'. Error: {e}. Validate that the file is not empty and is formatted in JSON.")
        return {"paul_commands": {}, "quote_reactions": {}}
    except Exception as e:
        logging.error(f"Unexpected error loading stats from '{stats_file}'. Error: {e}.")
        return {"paul_commands": {}, "quote_reactions": {}}
    
# Save stats to file
def save_stats (stats):
    try:
        with open(stats_file, 'w') as file:
            json.dump(stats, file, indent=4)
    except OSError as e:
        logging.error(f"OSError: Failed to save stats to '{stats_file}'. Error: {e}.")
    except Exception as e:
        logging.error(f"Failed to save stats to '{stats_file}'. Error: {e}.")

# Add a new quote
def add_quote(quote):
    try:
        quotes.append(quote)
        save_quotes(quotes)
    except AttributeError as e:
        logging.error(f"AttributeError: Failed to add quote. Error: {e}.")
    except Exception as e:
        logging.error(f"Failed to add quote to '{quotes_file}'. Error: {e}")

quotes = load_quotes()  # Load existing quotes from file
stats = load_stats()    # Load existing stats from file

# Trigger event once bot is connected to Discord to notify server that it is ready
@client.event
async def on_ready():
    logging.info(f"Logged in as {client.user.name}")
    logging.info(f"{client.user.name} is ready to receive commands!")

# Fetch previous content for statistics
async def fetch_message_stats(channel):
    try:
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
    except discord.HTTPException as e:
        logging.error(f"HTTPException: Error fetching message stats. Error: {e}.")
    except discord.Forbidden as e:
        logging.error(f"Forbidden: Insufficient permissions to fetch message stats. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexcepted error fetching message stats. Error: {e}.")
                
# Trigger events based on commands types in Discord messages
@client.event
async def on_message(message):
    try:
        logging.info(f"Received message: '{message.content}'")
        
        if message.author == client.user:
            return  #ignore messages that this generates

        # Convert the message content to lowercase for processing
        content = message.content.lower()

        # Display a test message to make sure the bot and Discord are working together well
        if '!test' in content:
            logging.info("Test message received.")
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
            embed.add_field(name="-------------", value="", inline=False)  # This adds a clear divider
            embed.add_field(name="Paul's Biggest Simp", value=f"{top_user_mention} with {most_commands} calls to PaulBot", inline=False)
            embed.add_field(name="-------------", value="", inline=False)  # This adds a clear divider
            embed.add_field(name="Most Popular Quote", value=f"With {most_reactions} Reactions:\n{top_quote}", inline=False)
            embed.add_field(name="-------------", value="", inline=False)  # This adds a clear divider
            embed.set_footer(text="Stats provided by PaulBot, about PaulBot, for you. He's a filthy self-reporter.")
            await message.channel.send(embed=embed)
    
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
    except discord.HTTPException as e:
        logging.error(f"HTTPException: Error processing Discord command. Error: {e}.")
    except discord.Forbidden as e:
        logging.error(f"Forbidden: Insufficient premissions to process Discord command. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error processing Discord command. Error: {e}.")

# Collect reaction statistics
@client.event
async def on_reaction_add(reaction, user):
    try:
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
    except discord.HTTPException as e:
        logging.error(f"HTTPException: Error processing reaction add. Error: {e}.")
    except discord.Forbidden as e:
        logging.error(f"Forbidden: Insufficient premissions to process reaction add from Discord. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error processing reaction add: {e}.")
        
# Remove reaction statistics
@client.event
async def on_reaction_remove(reaction, user):
    try:
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
    except discord.HTTPException as e:
        logging.error(f"HTTPException: Error processing reaction remove. Error: {e}.")
    except discord.Forbidden as e:
        logging.error(f"Forbidden: Insufficient premissions to process reaction remove from Discord. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error processing reaction remove: {e}.")

# Run the Discord bot with the loaded token
if __name__ == "__main__":        
    try:        
        client.run(TOKEN)
    except discord.LoginFailure as e:
        logging.error(f"LoginFailure: Invalid Discord token provided. Error: {e}.")
    except discord.PrivilegedIntentsRequired as e:
        logging.error(f"PrivilegedIntentsRequired: Missing required privileged intents. Enable them in the Discord Developer Portal. Error: {e}.")
    except discord.HTTPException as e:
        logging.error(f"HTTPException: HTTP request to Discord API failed. Error: {e}.")
    except discord.GatewayNotFound as e:
        logging.error(f"GatewayNotFound: Discord gateway was not found. Error: {e}.")
    except discord.ConnectionClosed as e:
        logging.error(f"ConnectionClosed: Connection to Discord closed unexpectedly. Error code: {e.code}. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error during bot run. Error: {e}.")