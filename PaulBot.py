import discord
import random
import json
import os
import logging
import pyttsx3
import re
from pydub import AudioSegment
from discord.ext import tasks, commands
from logging.handlers import RotatingFileHandler
from functools import wraps
from dotenv import load_dotenv

# Setup a logging function to process error handling throughout the script
def setup_logging():
    # Configure logging to a file
    logging.basicConfig(
       level=logging.INFO,
       format='%(asctime)s - %(levelname)s - %(message)s',
       handlers=[
           RotatingFileHandler('paulbot.log', maxBytes=1024*1024, backupCount=5),
           logging.StreamHandler()
           ]
    )
    
# Initialize logging
setup_logging()    

# Initialize TTS engine
try:
    tts_engine = pyttsx3.init()
    tts_engine.setProperty('rate',150)
    logging.info("TTS engine initialized successfully.")
except ImportError as e:
    logging.error(f"ImportError: pyttsx3 module not found. Error: {e}")
    tts_engine = None
except RuntimeError as e:
    logging.error(f"RuntimeError: Failed to initialize the TTS engine. Error: {e}")
    tts_engine = None
except Exception as e:
    logging.error(f"Unexpected error initializing the TTS engine. Error: {e}")
    tts_engine = None

# Function to handle file operations with error handling and logging
def handle_file_operation(file_path, operation_func, *args, **kwargs):
    try:
        return operation_func(file_path, *args, **kwargs)
    except FileNotFoundError:
        logging.error(f"FileNotFoundError: File '{file_path}' not found. Error: {e}.")
        return None
    except json.JSONDecodeError as e:
        logging.error(f"JSONDecodeError: Failed to decode JSON in '{file_path}'. Error: {e}. Validate that file is not empty and is formatted in JSON.")
        return None
    except OSError as e:
        logging.error(f"OSError: Failed to perform operation on '{file_path}'. Error: {e}.")
        return None
    except Exception as e:
        logging.error(f"Unexpected error during file operation on '{file_path}'. Error: {e}.")
        return None
    
# Helper function to check if a string contains a URL
def contains_url(text):
    url_pattern = re.compile(r'(https?://\S+|www\.\S+)')
    return url_pattern.search(text) is not None

# Decorator for handling Discord-specific exceptions
def discord_exception_handler(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except discord.HTTPException as e:
            logging.error(f"HTTPException in {func.__name__}: {e}")
        except discord.Forbidden as e:
            logging.error(f"Forbidden in {func.__name__}: {e}")
        except discord.NotFound as e:
            logging.error(f"NotFound in {func.__name__}: {e}")
        except Exception as e:
            logging.error(f"Unexpected error in {func.__name__}: {e}")
    return wrapper

# Load environment variables for Discord token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
VOICE_CHANNEL_ID = int(os.getenv('DISCORD_VOICE_CHANNEL_ID'))

# Check if the token is loaded correctly
if TOKEN is None:
    logging.error("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
    raise ValueError("No Discord token found. Please set the DISCORD_TOKEN environment variable.")
if GUILD_ID is None:
    logging.error("No Guild ID found. Please set the DISCORD_GUILD_ID environment variable.")
    raise ValueError("No Guild ID found. Please set the DISCORD_GUILD_ID environment variable.")
if VOICE_CHANNEL_ID is None:
    logging.error("No Channel ID found. Please set the VOICE_CHANNEL_ID environment variable.")
    raise ValueError("No Channel ID found. Please set the VOICE_CHANNEL_ID environment variable.")

# Define your intents (Discord security)
intents = discord.Intents.none()
intents.messages = True  # Enable message events
intents.message_content = True  # Enable message content
intents.reactions = True # Enable reaction events
intents.guilds = True # Enable server data so the bot can join voice chat

bot = commands.Bot(command_prefix='!', intents=intents)

quotes_file = 'quotes.json'  # File to store quotes
stats_file = 'stats.json'   # File to store stats

#Helper functions for file operations
def load_json_file(path):
    with open(path, 'r') as file:
        return json.load(file)
    
def save_json_file(path, data):
    with open(path, 'w') as file:
        json.dump(data, file, indent=4)

# Load existing quotes from file
def load_quotes():
    return handle_file_operation(quotes_file, load_json_file) or []

# Save quotes to file
def save_quotes(quotes):
    handle_file_operation(quotes_file, save_json_file, quotes)
        
# Load existing stats from file
def load_stats():
    default_stats = {"paul_commands": {}, "quote_reactions": {}}
    return handle_file_operation(stats_file, load_json_file) or default_stats
    
# Save stats to file
def save_stats (stats):
    handle_file_operation(stats_file, save_json_file, stats)

# Add a new quote
def add_quote(quote):
    try:
        quotes.append(quote)
        save_quotes(quotes)
    except AttributeError as e:
        logging.error(f"AttributeError: Failed to add quote '{quote}' to '{quotes_file}'. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error adding quote '{quote}' to '{quotes_file}'. Error: {e}")

quotes = load_quotes()  # Load existing quotes from file
stats = load_stats()    # Load existing stats from file

# Fetch previous content for statistics
@discord_exception_handler    
async def fetch_message_stats(channel):
    if stats.get("fetch_completed", False) == True:
        await channel.send("Fetch already completed. Skipping fetch.")
        return
    logging.info(f"Fetching message stats from channel: {channel.name}")    
    async for message in channel.history(limit=None):   # Fetch all messages in the channel after the last fetch command
        content = message.content.lower()
               
        # Track !paul command usage
        if message.author != bot.user and '!paul' in content:
            user_id = str(message.author.id)
            try:
                stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
                save_stats(stats)   # Save updated stats here
            except KeyError as e:
                logging.error(f"KeyError updating paul_commands for user: {user_id} during !fetch process. Error: {e}")
            except OSError as e:
                logging.error(f"OSError saving stats while tracking !paul usage for user '{user_id}' during !fetch process. Error: {e}")
            except Exception as e:
                logging.error(f"Unexpected error while tracking !paul usage for user '{user_id}' during !fetch process. Error: {e}")
            continue    #Skip further processing for non-PaulBot messages
            
        # Track reactions to quotes
        if message.author == bot.user:
            for quote in quotes:
                if quote.lower() in content:
                    try:    
                        # Check if the message has reactions
                        reactions_count = sum(reaction.count for reaction in message.reactions)
                        if reactions_count > 0:
                            # Aggregate reactions for each occurrence of the quote
                            if quote in stats["quote_reactions"]:
                                stats["quote_reactions"][quote]["reactions"] += reactions_count
                            else:
                                stats["quote_reactions"][quote] = {"content": quote, "reactions": reactions_count}
                            save_stats(stats)  # Save updated stats here
                    except KeyError as e:
                        logging.error(f"KeyError updating quote_reactions for quote {quote} during !fetch process. Error: {e}")
                    except OSError as e:
                        logging.error(f"OSError saving stats while tracking reactions for quote {quote} during !fetch process. Error: {e}")
                    except Exception as e:
                        logging.error(f"Unexpected error while tracking reactions for quote {quote} during !fetch process. Error: {e}")
        
    # Set the fetch_completed flag to True after processing
    stats["fetch_completed"] = True
    save_stats(stats)   # Save updated stats here
        
    # Post confirmation to channel
    await channel.send('Fetched stats from message history.')

# Trigger event once bot is connected to Discord to notify server that it is ready
@bot.event
@discord_exception_handler
async def on_ready():
    logging.info(f"Logged in as {bot.user.name}")
    logging.info(f"{bot.user.name} is ready to receive commands!")
    
    # Join the voice channel specified in the environment variables
    guild = bot.get_guild(GUILD_ID)
    channel = guild.get_channel(VOICE_CHANNEL_ID)
    
    if guild and channel:
        if not bot.voice_clients:
            await channel.connect()
            logging.info(f"Joined voice channel: {channel.name}")
    else:
        logging.error(f"Guild or voice channel not found. Unable to connect.")
        
    read_quotes.start()
        
# Task to read quotes at intervals
@tasks.loop(minutes=1)  # Change interval as desired
async def read_quotes():
    if not tts_engine:
        logging.error("TTS engine is not initialized. Skipping reading quotes.")
        return
    
    if bot.voice_clients:
        voice_client = bot.voice_clients[0]
        filtered_quotes = [quote for quote in quotes if not contains_url(quote)]
        if filtered_quotes:
            quote = random.choice(filtered_quotes)
            tts_engine.save_to_file(quote, 'quote.mp3')
            tts_engine.runAndWait()
            
            audio = AudioSegment.from_mp3('quote.mp3')
            audio.export('quote.wav', format='wav')
            
            source = discord.FFmpegPCMAudio('quote.wav')
            if voice_client.is_connected() and not voice_client.is_playing():
                voice_client.play(source)
                
            # Clean up temporary files
            os.remove('quote.mp3')    
            os.remove('quote.wav')
            
# Trigger events based on commands types in Discord messages
@bot.event
@discord_exception_handler
async def on_message(message):
    logging.info(f"Received message: '{message.content}' from user: '{message.author}'")
        
    if message.author == bot.user:
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
            try:
                add_quote(quote)
                await message.channel.send('Quote added!')
            except IOError as e:
                logging.error(f"IOError while adding quote: {quote}. Error: {e}")
                await message.channel.send('Failed to add quote due to a file error.')
            except Exception as e:
                logging.error(f"Unexpected error while adding quote: {quote}. Error: {e}")
                await message.channel.send('Failed to add quote due to an unexpected error.')
        else:
            await message.channel.send('Please provide a quote.')

    # Generate and sent a random quote to the Discord channel
    elif '!paul' in content:
        user_id = str(message.author.id)
        try:
            stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
            save_stats(stats)   # Save updated stats here
        except KeyError as e:
            logging.error(f"KeyError updating stats for user: {user_id} during !paul command processing. Error: {e}")
        except OSError as e:
            logging.error(f"OSError saving stats for user: {user_id} during !paul command processing. Error: {e}")
        except Exception as e:
            logging.error(f"Unexpected error updating stats for user: {user_id} during !paul command processing. Error: {e}")
    
        if quotes:
            try:
                random_quote = random.choice(quotes)
                sent_message = await message.channel.send(random_quote)
            except Exception as e:
                logging.error(f"Unexpected error sending random quote: {e}")
                await message.channel.send('Failed to send random quote due to an unexpected error.')
        else:
            await message.channel.send('No quotes available.')
            
    elif '!stats' in content:
        try:
            # How many quotes are currently in the quotes.json file
            total_quotes = len(quotes)
            # Who has sent !paul commands the most
            if stats["paul_commands"]:
                top_user_id = max(stats["paul_commands"], key=stats["paul_commands"].get)
                top_user = await bot.fetch_user(int(top_user_id))
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
        except KeyError as e:
            logging.error(f"KeyError accessing stats: {e}")
            await message.channel.send('Failed to retrieve stats due to a KeyError.')
        except discord.NotFound as e:
            logging.error(f"User not found while fetching stats: {e}")
            await message.channel.send('Failed to retrieve user for stats: User Not Found.')
        except discord.HTTPException as e:
            logging.error(f"HTTPException while fetching stats: {e}")
            await message.channel.send('Failed to retrieve stats due to an HTTP error.')
        except Exception as e:
            logging.error(f"Unexpected error retrieving stats: {e}")
            await message.channel.send('Failed to retrieve stats due to an unexpected error.')
    # Fetch message statistics retroactively
    elif '!fetch' in content:
        try:
            await fetch_message_stats(message.channel)
        except Exception as e:
            logging.error(f"Error fetching message stats for channel: {message.channel.id}. Error: {e}")
            await message.channel.send('Failed to fetch message stats.')
        
    # Display a list of available commands to the end user in Discord
    elif '!help' in content:
        try:
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
        except Exception as e:
            logging.error(f"Unexpected error sending help message: {e}.")
            await message.channel.send('Failed to send help message due to an unexpected error.')

# Collect reaction statistics
@bot.event
async def on_reaction_add(reaction, user):
    try:
        if user == bot.user:
            return      # Ignore reactions that PaulBot generates
    
        message = reaction.message
        content = message.content.lower()
    
        if message.author == bot.user:
            for quote in quotes:
                if quote.lower() in content:
                    if quote in stats["quote_reactions"]:
                        stats["quote_reactions"][quote]["reactions"] += 1
                    else:
                        stats["quote_reactions"][quote] = {"content": quote, "reactions": 1}
                    save_stats(stats) # Save stats here
                    break   # Stop checking quotes once a match is found
    except discord.HTTPException as e:
        logging.error(f"HTTPException: Error processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except discord.Forbidden as e:
        logging.error(f"Forbidden: Insufficient permissions to process reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except KeyError as e:
        logging.error(f"KeyError: Attempted to access a non-existent key while processing reaction addition for message ID {message.id} by user ID {user.id}. Key: {e}.")
    except TypeError as e:
        logging.error(f"TypeError: Encountered a type error while processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except OSError as e:
        logging.error(f"OSError: Failed to save stats while processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
        
# Remove reaction statistics
@bot.event
async def on_reaction_remove(reaction, user):
    try:
        if user == bot.user:
            return      # Ignore reactions that PaulBot generates
    
        message = reaction.message
        content = message.content.lower()
    
        if message.author == bot.user:
            for quote in quotes:
                if quote.lower() in content:
                    if quote in stats["quote_reactions"] and stats["quote_reactions"][quote]["reactions"] > 0:
                        stats["quote_reactions"][quote]["reactions"] -= 1
                        if stats["quote_reactions"][quote]["reactions"] == 0:
                            del stats["quote_reactions"][quote]
                        save_stats(stats)   #Save stats here
                    break   # Stop checking quotes once a match is found
    except discord.HTTPException as e:
        logging.error(f"HTTPException: Error processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except discord.Forbidden as e:
        logging.error(f"Forbidden: Insufficient permissions to process reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except KeyError as e:
        logging.error(f"KeyError: Attempted to access a non-existent key while processing reaction removal for message ID {message.id} by user ID {user.id}. Key: {e}.")
    except TypeError as e:
        logging.error(f"TypeError: Encountered a type error while processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except OSError as e:
        logging.error(f"OSError: Failed to save stats while processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except Exception as e:
        logging.error(f"Unexpected error processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")

# Run the Discord bot with the loaded token
if __name__ == "__main__":      # Ensure that bot is being run directly instead of inside another script  
    try:        
        bot.run(TOKEN)
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