import os
import chainlit as cl
from dotenv import load_dotenv, find_dotenv
import logging
from typing import List, Dict, Optional
import json
import re
from datetime import datetime
import socket

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_dependencies() -> bool:
    """
    Checks if required packages are installed.
    Returns:
        bool: True if all dependencies are present, False otherwise.
    """
    required = ['deep_translator', 'chainlit', 'dotenv']
    missing = []
    for module in required:
        try:
            __import__(module)
        except ImportError:
            missing.append(module)
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        return False
    return True

def check_internet() -> bool:
    """
    Checks if the system has an active internet connection.
    Returns:
        bool: True if connected, False otherwise.
    """
    try:
        socket.create_connection(("translate.google.com", 443), timeout=5)
        logger.info("Internet connection verified.")
        return True
    except (socket.gaierror, socket.timeout) as e:
        logger.error(f"No internet connection: {str(e)}")
        return False

def load_environment() -> bool:
    """
    Loads environment variables from .env file.
    Returns:
        bool: True if successful, False otherwise.
    """
    try:
        return load_dotenv(find_dotenv())
    except Exception as e:
        logger.error(f"Failed to load environment variables: {str(e)}")
        return False

def initialize_translators() -> Dict[str, Optional[object]]:
    """
    Initializes translators for English-to-Urdu and Urdu-to-English.
    Returns:
        Dict[str, Optional[object]]: Dictionary of translator instances.
    """
    try:
        from deep_translator import GoogleTranslator
        translators = {
            'en_to_ur': GoogleTranslator(source='en', target='ur'),
            'ur_to_en': GoogleTranslator(source='ur', target='en')
        }
        logger.info("Translators initialized.")
        return translators
    except ImportError:
        logger.error("deep-translator package is not installed.")
        return {}
    except Exception as e:
        logger.error(f"Failed to initialize translators: {str(e)}")
        return {}

def validate_input(text: str) -> bool:
    """
    Validates if the input text is non-empty and contains valid characters.
    Args:
        text (str): Input text to validate.
    Returns:
        bool: True if valid, False otherwise.
    """
    if not text or not text.strip():
        return False
    pattern = r'^[\w\s.,!?\'\"-]+$|^[\u0600-\u06FF\s.,!?]+$'
    return bool(re.match(pattern, text))

def detect_language(text: str) -> str:
    """
    Detects if the input text is English or Urdu based on character set.
    Args:
        text (str): Input text to analyze.
    Returns:
        str: 'en' for English, 'ur' for Urdu, or 'unknown' if unclear.
    """
    try:
        if re.search(r'[\u0600-\u06FF]', text):
            return 'ur'
        if re.search(r'[a-zA-Z]', text):
            return 'en'
        return 'unknown'
    except Exception as e:
        logger.error(f"Language detection failed: {str(e)}")
        return 'unknown'

def translate_text(translators: Dict[str, object], text: str) -> str:
    """
    Translates text based on detected language.
    Args:
        translators (Dict[str, object]): Dictionary of translator instances.
        text (str): Text to translate.
    Returns:
        str: Translated text or error message.
    """
    try:
        if not translators:
            return "Error: Translators not initialized."
        if not check_internet():
            return "Error: No internet connection. Please check your network."
        if not validate_input(text):
            return "Error: Please provide valid English or Urdu text."
        
        source_lang = detect_language(text)
        if source_lang == 'unknown':
            return "Error: Unable to detect language. Use clear English or Urdu text."
        
        translator_key = 'en_to_ur' if source_lang == 'en' else 'ur_to_en'
        target_lang = 'Urdu' if source_lang == 'en' else 'English'
        translated = translators[translator_key].translate(text)
        logger.info(f"Translated '{text}' ({source_lang}) to '{translated}'")
        return f"Translation to {target_lang}: {translated}"
    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        return f"Error: Unable to translate. Check your internet connection. ({str(e)})"

def save_history_to_file(history: List[Dict[str, str]]) -> None:
    """
    Saves translation history to a JSON file.
    Args:
        history (List[Dict[str, str]]): List of translation history entries.
    """
    try:
        with open('translation_history.json', 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False)
        logger.info("Translation history saved.")
    except Exception as e:
        logger.error(f"Failed to save history: {str(e)}")

def load_history_from_file() -> List[Dict[str, str]]:
    """
    Loads translation history from a JSON file.
    Returns:
        List[Dict[str, str]]: Loaded history or empty list if file doesn't exist.
    """
    try:
        if os.path.exists('translation_history.json'):
            with open('translation_history.json', 'r', encoding='utf-8') as f:
                history = json.load(f)
                logger.info("Translation history loaded.")
                return history
        return []
    except Exception as e:
        logger.error(f"Failed to load history: {str(e)}")
        return []

def get_current_timestamp() -> str:
    """
    Returns the current timestamp as a string.
    Returns:
        str: Formatted timestamp.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

@cl.on_chat_start
async def handle_chat_start():
    """
    Initializes the chat session for the translator.
    """
    if not check_dependencies():
        await cl.Message(content="Error: Missing dependencies. Run 'pip install deep-translator chainlit python-dotenv'.").send()
        return

    if not load_environment():
        await cl.Message(content="Error: Failed to load environment variables.").send()
        return

    if not check_internet():
        await cl.Message(content="Error: No internet connection. Please check your network.").send()
        return

    translators = initialize_translators()
    if not translators:
        await cl.Message(content="Error: Could not initialize translators.").send()
        return

    cl.user_session.set("translators", translators)
    cl.user_session.set("history", load_history_from_file())

    welcome_message = (
        "Welcome to Translation Buddy! Type English or Urdu text, and I'll translate it to the other language. "
        "Use '/history' to view past translations or '/clear' to reset history."
    )
    await cl.Message(content=welcome_message).send()

@cl.on_message
async def handle_message(message: cl.Message):
    """
    Handles incoming user messages and processes translation or commands.
    Args:
        message (cl.Message): User's input message.
    """
    history = cl.user_session.get("history", [])
    translators = cl.user_session.get("translators")
    user_input = message.content.strip()

    logger.info(f"Received user input: {user_input}")

    try:
        history.append({"role": "user", "content": user_input, "timestamp": get_current_timestamp()})

        if user_input.lower().startswith('/'):
            response = await process_command(user_input)
        else:
            response = translate_text(translators, user_input)

        await cl.Message(content=response).send()

        history.append({"role": "assistant", "content": response, "timestamp": get_current_timestamp()})
        cl.user_session.set("history", history[-10:])
        save_history_to_file(history)

    except Exception as e:
        error_message = f"Error: {str(e)}"
        logger.error(error_message)
        await cl.Message(content=error_message).send()
        history.append({"role": "assistant", "content": error_message, "timestamp": get_current_timestamp()})
        cl.user_session.set("history", history[-10:])
        save_history_to_file(history)

async def process_command(command: str) -> str:
    """
    Processes user commands like /history or /clear.
    Args:
        command (str): User command.
    Returns:
        str: Response to the command.
    """
    command = command.lower().strip()
    if command == '/history':
        history = cl.user_session.get("history", [])
        if not history:
            return "No translation history available."
        return "\n".join([f"{entry['timestamp']} [{entry['role']}]: {entry['content']}" for entry in history])
    
    elif command == '/clear':
        cl.user_session.set("history", [])
        logger.info("Session history cleared.")
        return "Translation history cleared."
    
    else:
        return "Unknown command. Available: /history, /clear"