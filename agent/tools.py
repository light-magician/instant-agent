import os
import subprocess
from typing import Any, Dict

from dotenv import load_dotenv
from tavily import TavilyClient

# Note: .env loading is handled in cli.py before imports

# Initialize Tavily client lazily to ensure .env is loaded first
_tavily_client = None

def get_tavily_client():
    """Get Tavily client, initializing if needed."""
    global _tavily_client
    if _tavily_client is None:
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("TAVILY_API_KEY environment variable not set")
        _tavily_client = TavilyClient(api_key=api_key)
    return _tavily_client

def search_web(query: str) -> str:
    """Search the web using Tavily API."""
    try:
        tavily = get_tavily_client()
        response = tavily.search(query=query, max_results=5)
        results = []
        for result in response.get('results', []):
            results.append(f"**{result['title']}**\n{result['content']}\nURL: {result['url']}\n")
        return "\n".join(results) if results else "No results found."
    except Exception as e:
        return f"Search error: {str(e)}"

def execute_shell(command: str) -> str:
    """Execute a shell command safely."""
    try:
        # Basic safety check - block dangerous commands
        dangerous_commands = ['rm -rf', 'sudo', 'chmod 777', 'dd if=', 'mkfs', 'fdisk']
        if any(dangerous in command.lower() for dangerous in dangerous_commands):
            return "Command blocked for safety reasons."
        
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        output = ""
        if result.stdout:
            output += f"STDOUT:\n{result.stdout}\n"
        if result.stderr:
            output += f"STDERR:\n{result.stderr}\n"
        output += f"Return code: {result.returncode}"
        
        return output
    except subprocess.TimeoutExpired:
        return "Command timed out after 30 seconds."
    except Exception as e:
        return f"Execution error: {str(e)}"
