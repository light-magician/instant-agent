import asyncio
from typing import List, Dict, Any, AsyncGenerator
from pydantic import BaseModel
from pydantic_ai import Agent
from agent.execution_engine import execution_memory, ExecutionStep
from agent.tools import search_web, execute_shell
from agent.agent import SYSTEM_PROMPT

class ResearchResult(BaseModel):
    """Research phase result."""
    summary: str
    key_findings: List[str]
    needs_more_research: bool = False
    confidence_level: float  # 0.0 to 1.0

class ExecutionPlan(BaseModel):
    """Execution plan with steps."""
    steps: List[Dict[str, str]]  # [{"description": "...", "action": "search|shell", "command": "..."}]
    estimated_difficulty: str  # "easy", "medium", "hard"
    requires_verification: bool = True

class StepVerification(BaseModel):
    """Verification of step execution."""
    success: bool
    confidence: float
    issues_found: List[str] = []
    should_retry: bool = False
    should_replan: bool = False
    next_action: str = "continue"  # continue, retry, replan, stop

# Specialized agents for Claude Code pattern
research_agent = Agent(
    'openai:gpt-4o-mini',
    result_type=ResearchResult,
    system_prompt=f"""{SYSTEM_PROMPT}

You are a research agent. Your job is to gather context and verify information before planning execution.

Research Guidelines:
- Use search to verify current information, best practices, and potential issues
- Identify unknowns that could cause execution failures
- Be thorough but concise
- Rate your confidence in the research findings

Focus on finding information that will help execution succeed."""
)

planning_agent = Agent(
    'openai:gpt-4o',
    result_type=ExecutionPlan,
    system_prompt=f"""{SYSTEM_PROMPT}

You are a planning agent. Create detailed, executable plans based on research.

Planning Guidelines:
- Break tasks into specific, actionable steps
- Each step should have clear success criteria
- Use standard Unix tools efficiently
- Consider potential failure points
- Keep steps focused and atomic

Available actions: "search" for web research, "shell" for command execution."""
)

verification_agent = Agent(
    'openai:gpt-4o-mini',
    result_type=StepVerification,
    system_prompt=f"""{SYSTEM_PROMPT}

You are a verification agent. Analyze execution results and determine next actions.

Verification Guidelines:
- Check if the step achieved its intended goal
- Identify any errors or issues in the output
- Decide if retry, replanning, or continuation is needed
- Be decisive but careful about failure modes

Rate success confidence and recommend clear next actions."""
)

async def claude_code_execution(user_query: str) -> AsyncGenerator[str, None]:
    """
    Claude Code-inspired execution pattern:
    Research → Plan → Execute → Verify → Iterate
    """
    
    # Start task in memory
    task_id = execution_memory.start_task(user_query)
    yield f"🔬 Starting research for: {user_query}\n"
    
    try:
        # Phase 1: Research
        research_context = f"""
        Query: {user_query}
        
        Previous execution context:
        {execution_memory.get_execution_context()}
        
        Research this query thoroughly. What information do you need to execute this successfully?
        """
        
        research_result = await research_agent.run(research_context)
        execution_memory.add_research(research_result.data.summary)
        
        yield f"📋 Research complete. Confidence: {research_result.data.confidence_level:.1%}\n"
        yield f"Key findings: {', '.join(research_result.data.key_findings[:3])}\n\n"
        
        if research_result.data.needs_more_research:
            yield "⚠️  Research indicates more information needed. Searching...\n"
            # Additional research search
            search_result = search_web(user_query)
            yield f"🔍 Additional research: {search_result[:200]}...\n\n"
        
        # Phase 2: Planning
        yield "📝 Creating execution plan...\n"
        
        planning_context = f"""
        Original Query: {user_query}
        Research Summary: {research_result.data.summary}
        Key Findings: {research_result.data.key_findings}
        
        Memory Context:
        {execution_memory.get_execution_context()}
        
        Create a detailed execution plan with specific steps.
        """
        
        plan_result = await planning_agent.run(planning_context)
        execution_memory.set_plan(plan_result.data.steps)
        
        yield f"✅ Plan created with {len(plan_result.data.steps)} steps\n"
        yield f"Estimated difficulty: {plan_result.data.estimated_difficulty}\n\n"
        
        # Phase 3: Execute → Verify → Iterate
        for i, step_data in enumerate(plan_result.data.steps, 1):
            yield f"📋 Step {i}: {step_data['description']}\n"
            
            # Get relevant memory for this step
            memory_context = execution_memory.get_relevant_memory(
                step_data['action'], 
                step_data['description']
            )
            
            if memory_context['failed_commands']:
                yield f"⚠️  Memory: Avoiding known failing commands\n"
            
            # Execute the step
            step = ExecutionStep(
                step_number=i,
                description=step_data['description'],
                action_type=step_data['action'],
                command=step_data.get('command')
            )
            
            max_retries = 3
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    if step.action_type == "search":
                        yield f"🔍 Searching: {step.command}\n"
                        step.result = search_web(step.command)
                    elif step.action_type == "shell":
                        yield f"⚡ Executing: {step.command}\n"
                        step.result = execute_shell(step.command)
                    else:
                        step.result = f"Unknown action type: {step.action_type}"
                    
                    # Verify the step
                    verification_context = f"""
                    Step: {step.description}
                    Command: {step.command}
                    Result: {step.result}
                    
                    Did this step succeed? Should we continue, retry, or replan?
                    """
                    
                    verification = await verification_agent.run(verification_context)
                    
                    step.success = verification.data.success
                    step.retry_count = retry_count
                    
                    if verification.data.success:
                        yield f"✅ Step completed successfully\n"
                        execution_memory.add_step_result(step)
                        break
                    else:
                        yield f"❌ Step failed: {', '.join(verification.data.issues_found)}\n"
                        
                        if verification.data.should_replan:
                            yield f"🔄 Replanning needed. Current approach not working.\n"
                            # TODO: Implement replanning logic
                            execution_memory.add_step_result(step)
                            return
                        elif verification.data.should_retry and retry_count < max_retries - 1:
                            retry_count += 1
                            yield f"🔄 Retrying step {i} (attempt {retry_count + 1})\n"
                            continue
                        else:
                            yield f"⚠️  Moving to next step despite failure\n"
                            execution_memory.add_step_result(step)
                            break
                
                except Exception as e:
                    yield f"❌ Error in step {i}: {str(e)}\n"
                    step.result = f"Error: {str(e)}"
                    step.success = False
                    retry_count += 1
                    if retry_count >= max_retries:
                        execution_memory.add_step_result(step)
                        break
            
            yield "\n"
        
        # Phase 4: Complete
        yield "🎯 Execution completed\n"
        final_result = f"Task '{user_query}' executed with {len(plan_result.data.steps)} steps"
        execution_memory.complete_task(final_result, success=True)
        yield f"✅ {final_result}\n"
        
    except Exception as e:
        error_msg = f"Execution failed: {str(e)}"
        execution_memory.complete_task(error_msg, success=False)
        yield f"❌ {error_msg}\n"