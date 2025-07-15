import sys
import os
import shutil
import argparse
from pathlib import Path

# Add the parent directory to the path so we can import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env BEFORE importing any agent modules
from dotenv import load_dotenv
import importlib.util

# Try to load .env from site-packages directory first
try:
    spec = importlib.util.find_spec("agent")
    if spec and spec.origin:
        package_dir = Path(spec.origin).parent.parent
        package_env = package_dir / ".env"
        if package_env.exists():
            load_dotenv(package_env)
        else:
            # Fallback to current directory
            load_dotenv()
    else:
        load_dotenv()
except:
    load_dotenv()

def setup_env_file(force_recreate=False):
    """Load .env from current directory or package installation."""
    from dotenv import load_dotenv
    
    # Strategy 1: Look for .env in current working directory (most common)
    current_dir = Path.cwd()
    env_file = current_dir / ".env"
    
    if env_file.exists():
        print(f"📁 Using .env from current directory: {env_file}")
        load_dotenv(env_file)
        
        # Verify keys are loaded
        openai_key = os.getenv("OPENAI_API_KEY")
        tavily_key = os.getenv("TAVILY_API_KEY")
        if openai_key and tavily_key:
            return True
        else:
            print(f"⚠️  .env file found but missing API keys")
    
    # Strategy 2: Look for .env in package installation directory
    try:
        import agent
        package_dir = Path(agent.__file__).parent.parent
        package_env = package_dir / ".env"
        
        if package_env.exists():
            print(f"📦 Using .env from package installation: {package_env}")
            load_dotenv(package_env)
            
            # Verify keys are loaded
            openai_key = os.getenv("OPENAI_API_KEY")
            tavily_key = os.getenv("TAVILY_API_KEY")
            if openai_key and tavily_key:
                return True
    except Exception as e:
        pass
    
    # Strategy 3: Create template .env in current directory
    if force_recreate or not env_file.exists():
        template = """# Instant Agent Configuration
OPENAI_API_KEY=your_openai_api_key_here
TAVILY_API_KEY=your_tavily_api_key_here
"""
        env_file.write_text(template)
        print(f"📝 Created .env template at: {env_file}")
    
    print("❌ No valid .env file found!")
    print("📝 Please edit the .env file with your actual API keys:")
    print("   OPENAI_API_KEY=your_actual_key")
    print("   TAVILY_API_KEY=your_actual_key")
    print(f"📍 Location: {env_file.absolute()}")
    return False

from agent.agent import process_request, clear_conversation, get_conversation_summary

def chat():
    """Basic chat interface for the agent."""
    print("Instant Agents CLI - Type 'quit' to exit")
    print("I can search the web and execute shell commands safely.")
    print("Commands: 'clear' to reset conversation, 'history' to see message count")
    print("-" * 60)
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
        
        # Special commands
        if user_input.lower() == 'clear':
            clear_conversation()
            print("Conversation history cleared.")
            continue
        
        if user_input.lower() == 'history':
            print(f"{get_conversation_summary()}")
            continue
            
        if not user_input:
            continue
            
        try:
            response = process_request(user_input)
            print(f"Agent: {response}")
                
        except Exception as e:
            print(f"Error: {str(e)}")
        
        print("-" * 60)  # Add divider between interactions

def main():
    parser = argparse.ArgumentParser(description='Instant Agents CLI')
    parser.add_argument('--reset-env', action='store_true', 
                       help='Force recreate .env file with template')
    args = parser.parse_args()
    
    # Check for .env file and setup if needed
    if not setup_env_file(force_recreate=args.reset_env):
        sys.exit(1)
    
    chat()

if __name__ == "__main__":
    main()