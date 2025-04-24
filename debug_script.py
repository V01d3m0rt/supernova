#!/usr/bin/env python

import sys
import logging
import traceback
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("debug")

# Add the current directory to the Python path
sys.path.insert(0, '.')

try:
    # Import the modules we need to test
    from supernova.cli.chat_session import ChatSession
    from supernova.cli.llm_interface import LLMInterface
    
    # Create a dummy API key
    api_key = "sk-mock-key"
    
    # Set up working directory
    working_dir = Path.cwd()
    
    # Create the LLM interface
    logger.info("Creating LLM interface...")
    llm = LLMInterface(
        api_key=api_key,
        model="gpt-4o",
        temperature=0.7,
        max_tokens="1000",  # Intentionally use a string to see if this is the issue
        logger=logger
    )
    
    # Format messages for the LLM
    logger.info("Formatting messages...")
    messages, tools, tool_choice = llm.format_messages_for_llm(
        content="hi",
        system_prompt="You are an AI assistant.",
        context_message="Working directory: /current/dir",
        previous_messages=[{"role": "user", "content": "Hello"}],
        tools=[]
    )
    
    # Try to send the formatted messages to the LLM
    logger.info("Sending to LLM...")
    response = llm.send_to_llm(
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        stream=False
    )
    
    logger.info("LLM response: %s", response)
    
except Exception as e:
    logger.error(f"Error: {str(e)}")
    logger.error(traceback.format_exc()) 