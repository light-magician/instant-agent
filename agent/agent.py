import os
from typing import Literal, List, Dict, Any

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from agent.tools import execute_shell, search_web

# Note: .env loading is handled in cli.py before imports
# Verify environment variables are loaded
import os
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️  OPENAI_API_KEY not found in environment")
if not os.getenv("TAVILY_API_KEY"):
    print("⚠️  TAVILY_API_KEY not found in environment")

# Load system prompt
def load_system_prompt() -> str:
    """Load the system prompt from file."""
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), "system_prompt.txt")
        with open(prompt_path, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return "You are a helpful AI assistant with access to web search and shell command execution tools."

SYSTEM_PROMPT = load_system_prompt()


# Main execution agent
main_agent = Agent(
    'openai:gpt-4',
    system_prompt=f"""{SYSTEM_PROMPT}

You have access to:
1. Web search via Tavily API - use search_web_tool(query)
2. Shell command execution - use execute_shell_tool(command)

Remember: Act efficiently and directly according to the guidelines above."""
)

# Add tools using decorators
@main_agent.tool_plain
def search_web_tool(query: str) -> str:
    """Search the web using Tavily API."""
    return search_web(query)

@main_agent.tool_plain
def execute_shell_tool(command: str) -> str:
    """Execute a shell command safely."""
    return execute_shell(command)

# Session management
class ConversationSession:
    def __init__(self):
        self.messages: List[Dict[str, str]] = []
    
    def add_user_message(self, content: str):
        """Add a user message to the conversation history."""
        self.messages.append({"role": "user", "content": content})
    
    def add_assistant_message(self, content: str):
        """Add an assistant message to the conversation history."""
        self.messages.append({"role": "assistant", "content": content})
    
    def get_recent_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent messages for context, limited to prevent token overflow."""
        return self.messages[-max_messages:] if self.messages else []
    
    def clear(self):
        """Clear conversation history."""
        self.messages.clear()

# Global session instance
current_session = ConversationSession()


def process_request(user_input: str):
    """Process a request and return response."""
    
    # Add user message to session history
    current_session.add_user_message(user_input)
    
    # Get recent context for better responses
    context_messages = current_session.get_recent_context()
    if context_messages:
        context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context_messages[-3:]])
        full_prompt = f"{context_str}\nuser: {user_input}"
    else:
        full_prompt = user_input
    
    # Get response from main agent
    response = main_agent.run_sync(full_prompt)
    
    # Add response to session history
    current_session.add_assistant_message(response.data)
    
    return response.data

def clear_conversation():
    """Clear the current conversation session."""
    current_session.clear()

def get_conversation_summary() -> str:
    """Get a summary of the current conversation."""
    if not current_session.messages:
        return "No conversation history."
    
    return f"Conversation has {len(current_session.messages)} messages."
