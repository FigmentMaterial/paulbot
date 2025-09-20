import discord
import random
import json
import os
import logging
import time
import re
import asyncio
import sys
from gtts import gTTS
from gtts.tokenizer import Tokenizer, pre_processors, tokenizer_cases
from pydub import AudioSegment
from discord.ext import tasks, commands
from logging.handlers import RotatingFileHandler
from functools import wraps
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# Setup a logging function to process error handling throughout the script
def setup_logging():
    # Load the desired log file path from environment variables (with a default fallback)
    log_file_path = os.getenv('LOG_FILE_PATH', '/app/logs/paulbot.log')
    log_level_str = os.getenv('LOG_LEVEL', 'INFO').upper()
    level = getattr(logging, log_level_str, logging.INFO)

    # Ensure the log directory exists, fall back safely if not writable
    log_dir = os.path.dirname(log_file_path)
    if log_dir:
        try:
            os.makedirs(log_dir, exist_ok=True)
        except Exception as e:
            fallback = 'paulbot.log'
            print(
                f"[setup_logging] WARNING: could not create '{log_dir}': {e}. "
                f"Falling back to '{fallback}'",
                file=sys.stderr
            )
            log_file_path = fallback

    fmt = '%(asctime)s %(levelname)s %(name)s [%(process)d] %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'
    formatter = logging.Formatter(fmt=fmt, datefmt=datefmt)

    file_handler = RotatingFileHandler(log_file_path, maxBytes=10_000_000, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)  # stdout is for visibility in 'docker logs'
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(level)

    # Force reconfigure root logger even if something configured it earlier
    logging.basicConfig(level=level, handlers=[file_handler, stream_handler], force=True)

    # Set reasonable defaults for noisy libraries
    logging.getLogger('discord').setLevel(logging.INFO)
    logging.getLogger('websockets').setLevel(logging.WARNING)

    # TEMPORARY: Debugging Discord voice issues
    logging.getLogger('discord.voice_client').setLevel(logging.DEBUG)
    logging.getLogger('discord.voice_state').setLevel(logging.DEBUG)
    logging.getLogger('discord.gateway').setLevel(logging.DEBUG)

    logging.getLogger(__name__).info(
        "Logging initialized level=%s file=%s (stdout + rotating file)",
        log_level_str, log_file_path
    )
    
# Initialize logging
setup_logging()

# Initialize ThreadPoolExecutor for offloading TTS work
executor = ThreadPoolExecutor(max_workers=2)

# Function to handle file operations with error handling and logging
def handle_file_operation(file_path, operation_func, *args, **kwargs):
    try:
        return operation_func(file_path, *args, **kwargs)
    except FileNotFoundError as e:
        logging.exception(f"FileNotFoundError: File '{file_path}' not found. Error: {e}.")
        return None
    except json.JSONDecodeError as e:
        logging.exception(f"JSONDecodeError: Failed to decode JSON in '{file_path}'. Error: {e}. Validate that file is not empty and is formatted in JSON.")
        return None
    except OSError as e:
        logging.exception(f"OSError: Failed to perform operation on '{file_path}'. Error: {e}.")
        return None
    except Exception as e:
        logging.exception(f"Unexpected error during file operation on '{file_path}'. Error: {e}.")
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
            logging.exception(f"HTTPException in {func.__name__}: {e}")
        except discord.Forbidden as e:
            logging.exception(f"Forbidden in {func.__name__}: {e}")
        except discord.NotFound as e:
            logging.exception(f"NotFound in {func.__name__}: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error in {func.__name__}: {e}")
    return wrapper

# Load environment variables for Discord token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('DISCORD_GUILD_ID')
VOICE_CHANNEL_ID = os.getenv('VOICE_CHANNEL_ID')

# Check if environment variables are loaded correctly
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
intents = discord.Intents.all()
#intents = discord.Intents.none()
#intents.messages = True  # Enable message events
#intents.message_content = True  # Enable message content
#intents.reactions = True # Enable reaction events
#intents.guilds = True # Enable server data so the bot can join voice chat

bot = commands.Bot(command_prefix='!', intents=intents)

# Set global voice fails to support reconnects for stale voice sessions
VOICE_FAIL_COUNT = 0
VOICE_FAIL_WINDOW_START = 0.0
voice_connect_lock = asyncio.Lock()
_last_connect_ts = 0.0
CONNECT_COOLDOWN = 20   # seconds between attempts; normal cooldown
SICK_BACKOFF = 90   # when Discord returns 4006 or empty modes

# Define permanent file storage for persistent quote storage and statistics
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
        logging.exception(f"AttributeError: Failed to add quote '{quote}' to '{quotes_file}'. Error: {e}.")
    except Exception as e:
        logging.exception(f"Unexpected error adding quote '{quote}' to '{quotes_file}'. Error: {e}")

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
                logging.exception(f"KeyError updating paul_commands for user: {user_id} during !fetch process. Error: {e}")
            except OSError as e:
                logging.exception(f"OSError saving stats while tracking !paul usage for user '{user_id}' during !fetch process. Error: {e}")
            except Exception as e:
                logging.exception(f"Unexpected error while tracking !paul usage for user '{user_id}' during !fetch process. Error: {e}")
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
                        logging.exception(f"KeyError updating quote_reactions for quote {quote} during !fetch process. Error: {e}")
                    except OSError as e:
                        logging.exception(f"OSError saving stats while tracking reactions for quote {quote} during !fetch process. Error: {e}")
                    except Exception as e:
                        logging.exception(f"Unexpected error while tracking reactions for quote {quote} during !fetch process. Error: {e}")
        
    # Set the fetch_completed flag to True after processing
    stats["fetch_completed"] = True
    save_stats(stats)   # Save updated stats here
        
    # Post confirmation to channel
    await channel.send('Fetched stats from message history.')

# Trigger event once bot is connected to Discord to notify server that it is ready
@bot.event
@discord_exception_handler
async def on_ready():
    logging.info("Logged in as %s", bot.user.name)
    logging.info("%s is ready to receive commands!", bot.user.name)
    
    # Convert environmental variables to integers
    try:
        guild_id = int(GUILD_ID)
        channel_id = int(VOICE_CHANNEL_ID)
    except Exception as e:
        logging.exception(f"Error converting IDs to integers: {e}")
        return
    
    ok = await reconnect_voice_client()
    if not ok:
        logging.error("Initial voice connect failed; read_quotes will keep retrying.")
    read_quotes.start()

# Helper function to check if a file is in use
def is_file_in_use(filepath):
    try:
        with open(filepath, 'a', os.O_EXCL):
            return False
    except IOError:
        return True
    
# Helper function to delete a file with retries - used for temporary audio files
def delete_file_with_retry(filepath, retries=5, delay=1):
    for attempt in range(retries):
        if not is_file_in_use(filepath):
            try:
                os.remove(filepath)
                return True
            except Exception as e:
                logging.exception(f"Attempt {attempt + 1}: Failed to delete {filepath}. Error: {e}")
        time.sleep(delay)
    logging.error(f"Failed to delete {filepath} after {retries} attempts.")
    return False

# Preprocess quote for gTTS tokenizing
def preprocess_text(quote):
    try:
        text = pre_processors.end_of_line(quote)
        text = pre_processors.tone_marks(quote)
        text = pre_processors.abbreviations(quote)
        text = pre_processors.word_sub(quote)
        text = ' '.join(quote.split())   # Normalizes whitespace
        return text
    except Exception as e:
        logging.exception(f"Error during pre-processing: {e}")
        return quote     # Return the original quote if processing fails
    
# Tokenize the quote
def tokenize_text (quote):
    try:
        preprocessed_quote = preprocess_text(quote)
        
        # Initialize Tokenizer with symbol rules
        tokenizer = Tokenizer([
            tokenizer_cases.tone_marks,
            tokenizer_cases.period_comma,
            tokenizer_cases.colon,
            tokenizer_cases.other_punctuation
            ])

        # Tokenize the preprocessed text, stripping out empty tokens to prevent errors
        tokens = [token.strip() for token in tokenizer.run(preprocessed_quote) if token.strip()]
        if not tokens:
            logging.warning("Tokenization resulted in no valid tokens. Falling back to original quote.")
            tokens = [quote]
        return tokens
    except Exception as e:
        logging.exception(f"Error during tokenization: {e}")
        return [quote] # Fallback to returning the original text

# Async wrapper for convert tts to mp3
async def async_convert_tts_to_mp3(quote):
    """Asynchronous wrapper for convert_tts_to_mp3."""
    loop = asyncio.get_event_loop()
    try:
        # Use partial to pass arguments to the synchronous function
        result = await loop.run_in_executor(executor, partial(convert_tts_to_mp3, quote))
        return result
    except Exception as e:
        logging.error(f"Error in async TTS conversion: {e}")
        return False

# Function to perform TTS conversion using gTTS
def convert_tts_to_mp3(quote):
    """Synchronous TTS conversion to MP3"""
    try:    
        # Tokenize the input text
        tokens = tokenize_text(quote)
        logging.info(f"Tokenized text into {len(tokens)} parts.")
        
        # Generate and combine audio for each token
        combined_audio = None
        for idx, token in enumerate(tokens):
            logging.info(f"Processing token {idx + 1}/{len(tokens)}: {token}")
            tts = gTTS(text=token, lang='en')
            temp_file = f'temp_token_{idx}.mp3'
            tts.save(temp_file)

            # Load the audio for the current token
            audio_segment = AudioSegment.from_file(temp_file)

            # Combine with previous audio
            if combined_audio is None:
                combined_audio = audio_segment
            else:
                combined_audio += audio_segment

            # Clean up temporary file
            os.remove(temp_file)

        # Save the combined audio
        if combined_audio:
            combined_audio.export("quote.mp3", format="mp3")
            logging.info("quote.mp3 was created successfully")
            return True
        else:
            logging.error("No audio was generated for the quote.")
            return False
        
    except Exception as e:
        logging.exception(f"Error converting quote to MP3 file: {e}")
        return False
        
# Task to read quotes at intervals
@tasks.loop(minutes=1)  # Change interval as desired
async def read_quotes():
    global VOICE_FAIL_COUNT, VOICE_FAIL_WINDOW_START
    try:
        guild = bot.get_guild(int(GUILD_ID))
        vc = discord.utils.get(bot.voice_clients, guild=guild)

        # Quick helper to track failures in a short window
        def mark_failure():
            global VOICE_FAIL_COUNT, VOICE_FAIL_WINDOW_START
            now = time.monotonic()
            if VOICE_FAIL_WINDOW_START == 0.0 or (now - VOICE_FAIL_WINDOW_START) > 180: # 3 minute window
                VOICE_FAIL_WINDOW_START = now
                VOICE_FAIL_COUNT = 1
            else:
                VOICE_FAIL_COUNT += 1

        # Ensure connected
        if not vc or not vc.is_connected():
            logging.warning("Voice client is not connected. Reconnecting...")
            ok = await reconnect_voice_client()
            if not ok:
                return
            # refresh vc reference after reconnect
            vc = discord.utils.get(bot.voice_clients, guild=guild)
            if not vc or not vc.is_connected():
                return

        # Prepare and play audio
        filtered_quotes = [quote for quote in quotes if not contains_url(quote)]
        if not filtered_quotes:
            logging.warning("No quotes available for playback.")
            return

        quote = random.choice(filtered_quotes)
        logging.info("Selected quote to read aloud: %s", quote)
            
        # Perform TTS conversion to MP3
        success = await async_convert_tts_to_mp3(quote)
        if not success:
            logging.error("quote.mp3 was not created successfully")
            mark_failure()
            return
            
        # Convert MP3 file to WAV
        try:
            audio = AudioSegment.from_mp3('quote.mp3')
            audio.export('quote.wav', format='wav')
        except Exception:
            logging.exception("Error converting MP3 to WAV")
            mark_failure()
            return

        # Add a short delay to ensure the file systems recognizes the new file.
        await asyncio.sleep(1)
            
        try:
            if not vc.is_connected():
                logging.warning("Lost voice connection before playback; skipping this tick.")
                mark_failure()
                return
            source = discord.FFmpegPCMAudio('quote.wav')
            if not vc.is_playing():
                vc.play(source)
                # Wait for the playback to finish before proceeding
                while vc.is_playing():
                    await asyncio.sleep(1)
        except Exception:
            logging.exception("Error in audio playback")
            mark_failure()
                
        finally:
            # Clean up temporary files
            try:
               delete_file_with_retry('quote.mp3')
               delete_file_with_retry('quote.wav')
            except Exception:
                logging.exception("Error cleaning up audio files")
    except Exception:
        logging.exception("Unexpected error in read_quotes loop")


async def reconnect_voice_client():
    global _last_connect_ts
    now = asyncio.get_running_loop().time()

    # Cooldown: avoid hammering when Discord is unhappy
    if now - _last_connect_ts < CONNECT_COOLDOWN:
        logging.debug("Reconnect suppressed by cooldown.")
        return False

    async with voice_connect_lock:
        now = asyncio.get_running_loop().time()
        if now - _last_connect_ts < CONNECT_COOLDOWN:
            logging.debug("Reconnect suppressed by cooldown (inside lock).")
            return False
        _last_connect_ts = now

        try:
            guild = bot.get_guild(int(GUILD_ID))
            channel = guild.get_channel(int(VOICE_CHANNEL_ID)) if guild else None
            if not guild or not channel:
                logging.error("Guild or voice channel not found.")
                return False

            vc = discord.utils.get(bot.voice_clients, guild=guild)
            if vc and vc.is_connected():
                logging.info("Voice already connected to: %s", getattr(vc.channel, "name", "?"))
                return True

            # If there is a stale VC object, clean it up
            if vc and not vc.is_connected():
                try:
                    await vc.disconnect(force=True)
                    logging.info("Stale voice client disconnected (force=True).")
                except Exception:
                    logging.exception("Error while force-disconnecting stale voice client.")

            # IMPORTANT: let us manage reconnects; disable library auto-reconnect
            MAX_TRIES = 3
            for attempt in range(1, MAX_TRIES +1):
                try:
                    await channel.connect(timeout=60, reconnect=False)
                    logging.info("Connected to voice channel %s", channel.name)
                    return True
                except discord.errors.ConnectionClosed as e:
                    # 4006 => session invalid; quarantine before next try
                    if getattr(e, "code", None) == 4006:
                        logging.warning("Voice session invalid (4006). Backing off for %ss", SICK_BACKOFF)
                        _last_connect_ts = asyncio.get_running_loop().time() - CONNECT_COOLDOWN + SICK_BACKOFF
                        return False
                    logging.exception("ConnectionClosed on attempt %s/%s (code=%s)", attempt, MAX_TRIES, getattr(e, "code", None))
                except Exception as e:
                    #Empty-modes signature shows as IndexError or 'modes[0]' in msg
                    msg = str(e)
                    if isinstance(e, IndexError) or "mode = modes[0]" in msg or "list index out of range" in msg:
                        logging.warning("Empty encryption modes from voice node. Backing off for %ss.", SICK_BACKOFF)
                        _last_connect_ts = asyncio.get_running_loop().time() - CONNECT_COOLDOWN + SICK_BACKOFF
                        return False
                    # Other transient issues (e.g., 522 handshake)
                    if "WSServerHandshakeError" in msg or "Invalid response status" in msg or "522" in msg:
                        logging.warning("Voice node handshake issue. Backing off for %ss.", SICK_BACKOFF)
                        _last_connect_ts = asyncio.get_running_loop().time() - CONNECT_COOLDOWN + SICK_BACKOFF
                        return False
                    logging.exception("Error during connection attempt %s/%s", attempt, MAX_TRIES)

                # back off with a little jitter
                await asyncio.sleep(5 + attempt*2)

            logging.error("Failed to connect to voice channel after %s attempts.", MAX_TRIES)
            return False

        except Exception:
            logging.exception("Unexpected error in reconnect_voice_client")
            return False
            
# Trigger events based on commands typed in Discord messages
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
                logging.exception(f"IOError while adding quote: {quote}. Error: {e}")
                await message.channel.send('Failed to add quote due to a file error.')
            except Exception as e:
                logging.exception(f"Unexpected error while adding quote: {quote}. Error: {e}")
                await message.channel.send('Failed to add quote due to an unexpected error.')
        else:
            await message.channel.send('Please provide a quote.')

    # Generate and send a random quote to the Discord channel
    elif '!paul' in content:
        user_id = str(message.author.id)
        try:
            stats["paul_commands"][user_id] = stats["paul_commands"].get(user_id, 0) + 1
            save_stats(stats)   # Save updated stats here
        except KeyError as e:
            logging.exception(f"KeyError updating stats for user: {user_id} during !paul command processing. Error: {e}")
        except OSError as e:
            logging.exception(f"OSError saving stats for user: {user_id} during !paul command processing. Error: {e}")
        except Exception as e:
            logging.exception(f"Unexpected error updating stats for user: {user_id} during !paul command processing. Error: {e}")
    
        if quotes:
            try:
                random_quote = random.choice(quotes)
                sent_message = await message.channel.send(random_quote)
            except Exception as e:
                logging.exception(f"Unexpected error sending random quote: {e}")
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
            logging.exception(f"KeyError accessing stats: {e}")
            await message.channel.send('Failed to retrieve stats due to a KeyError.')
        except discord.NotFound as e:
            logging.exception(f"User not found while fetching stats: {e}")
            await message.channel.send('Failed to retrieve user for stats: User Not Found.')
        except discord.HTTPException as e:
            logging.exception(f"HTTPException while fetching stats: {e}")
            await message.channel.send('Failed to retrieve stats due to an HTTP error.')
        except Exception as e:
            logging.exception(f"Unexpected error retrieving stats: {e}")
            await message.channel.send('Failed to retrieve stats due to an unexpected error.')
    # Fetch message statistics retroactively
    elif '!fetch' in content:
        try:
            await fetch_message_stats(message.channel)
        except Exception as e:
            logging.exception(f"Error fetching message stats for channel: {message.channel.id}. Error: {e}")
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
            logging.exception(f"Unexpected error sending help message: {e}.")
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
        logging.exception(f"HTTPException: Error processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except discord.Forbidden as e:
        logging.exception(f"Forbidden: Insufficient permissions to process reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except KeyError as e:
        logging.exception(f"KeyError: Attempted to access a non-existent key while processing reaction addition for message ID {message.id} by user ID {user.id}. Key: {e}.")
    except TypeError as e:
        logging.exception(f"TypeError: Encountered a type error while processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except OSError as e:
        logging.exception(f"OSError: Failed to save stats while processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except Exception as e:
        logging.exception(f"Unexpected error processing reaction addition for message ID {message.id} by user ID {user.id}. Error: {e}.")
        
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
        logging.exception(f"HTTPException: Error processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except discord.Forbidden as e:
        logging.exception(f"Forbidden: Insufficient permissions to process reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except KeyError as e:
        logging.exception(f"KeyError: Attempted to access a non-existent key while processing reaction removal for message ID {message.id} by user ID {user.id}. Key: {e}.")
    except TypeError as e:
        logging.exception(f"TypeError: Encountered a type error while processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except OSError as e:
        logging.exception(f"OSError: Failed to save stats while processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")
    except Exception as e:
        logging.exception(f"Unexpected error processing reaction removal for message ID {message.id} by user ID {user.id}. Error: {e}.")

# Run the Discord bot with the loaded token
if __name__ == "__main__":      # Ensure that bot is being run directly instead of inside another script  
    try:        
        bot.run(TOKEN)
    except discord.LoginFailure as e:
        logging.exception(f"LoginFailure: Invalid Discord token provided. Error: {e}.")
    except discord.PrivilegedIntentsRequired as e:
        logging.exception(f"PrivilegedIntentsRequired: Missing required privileged intents. Enable them in the Discord Developer Portal. Error: {e}.")
    except discord.HTTPException as e:
        logging.exception(f"HTTPException: HTTP request to Discord API failed. Error: {e}.")
    except discord.GatewayNotFound as e:
        logging.exception(f"GatewayNotFound: Discord gateway was not found. Error: {e}.")
    except discord.ConnectionClosed as e:
        logging.exception(f"ConnectionClosed: Connection to Discord closed unexpectedly. Error code: {e.code}. Error: {e}.")
    except Exception as e:
        logging.exception(f"Unexpected error during bot run. Error: {e}.")
