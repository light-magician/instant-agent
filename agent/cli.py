import asyncio
import sys
import os

# Add the parent directory to the path so we can import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.agent import process_request_streaming

async def chat():
    """Basic chat interface for the agent."""
    print("Instant Agents CLI - Type 'quit' to exit")
    print("I can search the web and execute shell commands safely.")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("Goodbye!")
            break
            
        if not user_input:
            continue
            
        try:
            print("Agent: ", end="", flush=True)
            
            # Use streaming for better UX
            accumulated_text = ""
            async for chunk in process_request_streaming(user_input):
                # Print only the new part of the text
                new_text = chunk[len(accumulated_text):]
                print(new_text, end="", flush=True)
                accumulated_text = chunk
                
        except Exception as e:
            print(f"\nError: {str(e)}")
        
        print()  # Add spacing between interactions

def main():
    asyncio.run(chat())

if __name__ == "__main__":
    main()