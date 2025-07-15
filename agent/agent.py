import os
from typing import Literal, List, Dict, Any

from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext

from agent.tools import execute_shell, search_web

load_dotenv()

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

class RequestClassification(BaseModel):
    """Classification of user request complexity."""
    type: Literal["simple", "complex"]
    reasoning: str
    needs_clarification: bool = False
    clarification_question: str | None = None

class PlanStep(BaseModel):
    """Individual step in a complex plan."""
    step_number: int
    description: str
    action_type: Literal["search", "shell", "clarify", "analysis"]
    command: str | None = None

class ComplexPlan(BaseModel):
    """Plan for handling complex requests."""
    steps: list[PlanStep]
    estimated_complexity: Literal["medium", "high"]
    requires_user_confirmation: bool = False

# Router agent to classify requests
router_agent = Agent(
    'openai:gpt-4o-mini',
    result_type=RequestClassification,
    system_prompt=f"""You are a request classifier following these principles:

{SYSTEM_PROMPT}

Classify requests as "simple" or "complex":

SIMPLE requests:
- Direct questions answerable immediately
- Single search queries or basic file operations
- Standard Unix commands (ls, cat, grep, find, etc.)
- Quick information lookups

COMPLEX requests:
- Multi-step tasks requiring planning
- Platform-specific operations needing research
- Tasks with unknowns requiring clarification
- Operations requiring multiple tools in sequence

Be concise in your reasoning. Mark needs_clarification=True only for genuine ambiguities."""
)

# Planning agent for complex requests
planning_agent = Agent(
    'openai:gpt-4o',
    result_type=ComplexPlan,
    system_prompt=f"""You are a planning agent following these principles:

{SYSTEM_PROMPT}

Break down complex requests into efficient step-by-step plans.

Available actions:
- "search": Web search for verification or current information
- "shell": Execute shell commands directly (use Unix tools naturally)
- "clarify": Ask user for clarification only when essential
- "analysis": Analyze results to determine next steps

Create concise, actionable steps. Use standard Unix commands without explanation.
Only ask for confirmation on genuinely destructive operations."""
)

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

async def process_request(user_input: str, stream_callback=None):
    """Process a user request through the agent system."""
    
    # Step 1: Classify the request
    classification = await router_agent.run(user_input)
    
    if classification.data.needs_clarification:
        return f"I need clarification: {classification.data.clarification_question}"
    
    if classification.data.type == "simple":
        # Handle simple requests directly with streaming if callback provided
        if stream_callback:
            async with main_agent.run_stream(user_input) as result:
                async for text in result.stream_text(debounce_by=0.01):
                    stream_callback(text)
            return result.data
        else:
            response = await main_agent.run(user_input)
            return response.data
    
    else:
        # Handle complex requests with planning
        plan = await planning_agent.run(user_input)
        
        if plan.data.requires_user_confirmation:
            plan_summary = "\n".join([f"{step.step_number}. {step.description}" for step in plan.data.steps])
            return f"I've created a plan for your request:\n\n{plan_summary}\n\nDo you want me to proceed? (yes/no)"
        
        # Execute the plan
        results = []
        for step in plan.data.steps:
            if step.action_type == "search" and step.command:
                result = search_web(step.command)
                results.append(f"Step {step.step_number}: {step.description}\nResult: {result}\n")
            elif step.action_type == "shell" and step.command:
                result = execute_shell(step.command)
                results.append(f"Step {step.step_number}: {step.description}\nResult: {result}\n")
            elif step.action_type == "clarify":
                return f"I need clarification for step {step.step_number}: {step.description}"
        
        return "\n".join(results)

async def process_request_streaming(user_input: str):
    """Process a request with streaming support - yields text chunks."""
    
    # Add user message to session history
    current_session.add_user_message(user_input)
    
    # Get recent conversation context
    conversation_context = current_session.get_recent_context()
    
    # Create context string from conversation history
    context_prompt = user_input
    if conversation_context:
        context_parts = []
        for msg in conversation_context[-6:]:  # Last 6 messages for context
            role = msg["role"].title()
            content = msg["content"][:200]  # Truncate long messages
            context_parts.append(f"{role}: {content}")
        context_prompt = f"Previous conversation:\n{chr(10).join(context_parts)}\n\nCurrent request: {user_input}"
    
    # Step 1: Classify the request (with context)
    classification = await router_agent.run(context_prompt)
    
    if classification.data.needs_clarification:
        response = f"I need clarification: {classification.data.clarification_question}"
        current_session.add_assistant_message(response)
        yield response
        return
    
    full_response = ""
    
    if classification.data.type == "simple":
        # Stream simple requests with conversation history
        async with main_agent.run_stream(context_prompt) as result:
            async for text in result.stream_text(debounce_by=0.01):
                yield text
                full_response = text
        
        # Add the complete response to session history
        current_session.add_assistant_message(full_response)
    else:
        # Use Claude Code-inspired execution engine for complex requests
        from agent.claude_engine import claude_code_execution
        
        execution_results = []
        async for chunk in claude_code_execution(user_input):
            yield chunk
            execution_results.append(chunk)
        
        # Add the complete execution results to session history
        current_session.add_assistant_message("".join(execution_results))

def clear_conversation():
    """Clear the current conversation session."""
    current_session.clear()

def get_conversation_summary() -> str:
    """Get a summary of the current conversation."""
    if not current_session.messages:
        return "No conversation history."
    
    return f"Conversation has {len(current_session.messages)} messages."
