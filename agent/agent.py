import os
from typing import Literal
from pydantic import BaseModel
from pydantic_ai import Agent, RunContext
from dotenv import load_dotenv
from agent.tools import search_web, execute_shell

load_dotenv()

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
    system_prompt="""You are a request classifier. Analyze user requests and classify them as either "simple" or "complex".

SIMPLE requests:
- Direct questions that can be answered immediately
- Single search queries ("search for X")
- Basic information requests
- Simple shell commands

COMPLEX requests:
- Multi-step tasks requiring planning
- Platform-specific operations (like moving files to specific apps)
- Tasks with potential unknowns that need clarification
- Requests requiring multiple tools or dependencies

Always provide clear reasoning for your classification. If the request has unknowns that could be clarified with a simple question, mark needs_clarification=True and provide the question."""
)

# Planning agent for complex requests
planning_agent = Agent(
    'openai:gpt-4o-mini',
    result_type=ComplexPlan,
    system_prompt="""You are a planning agent. Break down complex requests into step-by-step plans.

Available actions:
- "search": Use web search to find information
- "shell": Execute shell commands (be careful with safety)
- "clarify": Ask user for clarification
- "analysis": Analyze results and determine next steps

Create detailed, actionable steps. Be specific about what commands to run or what to search for.
Consider safety and ask for confirmation on potentially destructive operations."""
)

# Main execution agent
main_agent = Agent(
    'openai:gpt-4o-mini',
    system_prompt="""You are a helpful assistant that can search the web and execute shell commands.

You have access to:
1. Web search via Tavily API
2. Safe shell command execution

Be helpful, accurate, and safe. Always explain what you're doing and why.
For shell commands, prioritize safety and explain potential risks."""
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
    
    # Step 1: Classify the request
    classification = await router_agent.run(user_input)
    
    if classification.data.needs_clarification:
        yield f"I need clarification: {classification.data.clarification_question}"
        return
    
    if classification.data.type == "simple":
        # Stream simple requests
        async with main_agent.run_stream(user_input) as result:
            async for text in result.stream_text(debounce_by=0.01):
                yield text
    else:
        # For complex requests, yield planning and execution updates
        yield "🤔 Planning your request...\n"
        
        plan = await planning_agent.run(user_input)
        
        if plan.data.requires_user_confirmation:
            plan_summary = "\n".join([f"{step.step_number}. {step.description}" for step in plan.data.steps])
            yield f"I've created a plan for your request:\n\n{plan_summary}\n\nDo you want me to proceed? (yes/no)"
            return
        
        # Execute the plan with status updates
        for step in plan.data.steps:
            yield f"\n📋 Step {step.step_number}: {step.description}\n"
            
            if step.action_type == "search" and step.command:
                yield "🔍 Searching...\n"
                result = search_web(step.command)
                yield f"Result: {result}\n"
            elif step.action_type == "shell" and step.command:
                yield f"⚡ Executing: {step.command}\n"
                result = execute_shell(step.command)
                yield f"Result: {result}\n"
            elif step.action_type == "clarify":
                yield f"❓ I need clarification for step {step.step_number}: {step.description}"
                return