import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel
from pydantic_ai import Agent

from agent.tools import execute_shell, search_web


@dataclass
class ExecutionStep:
    step_number: int
    description: str
    action_type: str  # "search", "shell", "analysis"
    command: Optional[str]
    result: Optional[str] = None
    success: bool = False
    timestamp: str = ""
    retry_count: int = 0

@dataclass
class TaskExecution:
    task_id: str
    original_query: str
    research_phase: Optional[str] = None
    plan: List[Dict] = None
    steps: List[ExecutionStep] = None
    current_step: int = 0
    status: str = "planning"  # planning, executing, completed, failed
    final_result: Optional[str] = None
    created_at: str = ""

class ExecutionMemory:
    def __init__(self, memory_file: str = "agent/execution_memory.json"):
        self.memory_file = memory_file
        self.current_execution: Optional[TaskExecution] = None
        self.persistent_memory = self._load_persistent_memory()
    
    def _load_persistent_memory(self) -> Dict:
        """Load persistent memory from file."""
        if os.path.exists(self.memory_file):
            try:
                with open(self.memory_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {
            "successful_patterns": [],
            "failed_patterns": [],
            "learned_commands": {},
            "task_history": []
        }
    
    def _save_persistent_memory(self):
        """Save persistent memory to file."""
        try:
            os.makedirs(os.path.dirname(self.memory_file), exist_ok=True)
            with open(self.memory_file, 'w') as f:
                json.dump(self.persistent_memory, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save memory: {e}")
    
    def start_task(self, query: str) -> str:
        """Start a new task execution."""
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_execution = TaskExecution(
            task_id=task_id,
            original_query=query,
            steps=[],
            created_at=datetime.now().isoformat()
        )
        return task_id
    
    def add_research(self, research_result: str):
        """Add research phase result."""
        if self.current_execution:
            self.current_execution.research_phase = research_result
    
    def set_plan(self, plan: List[Dict]):
        """Set the execution plan."""
        if self.current_execution:
            self.current_execution.plan = plan
            self.current_execution.status = "executing"
    
    def add_step_result(self, step: ExecutionStep):
        """Add a completed step result."""
        if self.current_execution:
            step.timestamp = datetime.now().isoformat()
            self.current_execution.steps.append(step)
            
            # Learn from success/failure
            if step.success:
                self._learn_successful_pattern(step)
            else:
                self._learn_failed_pattern(step)
    
    def _learn_successful_pattern(self, step: ExecutionStep):
        """Learn from successful execution patterns."""
        pattern = {
            "action_type": step.action_type,
            "description_keywords": step.description.lower().split()[:5],
            "command": step.command,
            "success_count": 1
        }
        
        # Check if similar pattern exists
        for existing in self.persistent_memory["successful_patterns"]:
            if (existing["action_type"] == pattern["action_type"] and 
                existing["command"] == pattern["command"]):
                existing["success_count"] += 1
                return
        
        self.persistent_memory["successful_patterns"].append(pattern)
        self._save_persistent_memory()
    
    def _learn_failed_pattern(self, step: ExecutionStep):
        """Learn from failed execution patterns."""
        pattern = {
            "action_type": step.action_type,
            "command": step.command,
            "error_context": step.result[:200] if step.result else "",
            "failure_count": 1
        }
        
        # Check if similar pattern exists
        for existing in self.persistent_memory["failed_patterns"]:
            if (existing["action_type"] == pattern["action_type"] and 
                existing["command"] == pattern["command"]):
                existing["failure_count"] += 1
                return
        
        self.persistent_memory["failed_patterns"].append(pattern)
        self._save_persistent_memory()
    
    def get_relevant_memory(self, action_type: str, description: str) -> Dict:
        """Get relevant memory for current action."""
        relevant = {
            "successful_commands": [],
            "failed_commands": [],
            "suggestions": []
        }
        
        keywords = description.lower().split()
        
        # Find relevant successful patterns
        for pattern in self.persistent_memory["successful_patterns"]:
            if pattern["action_type"] == action_type:
                if any(kw in pattern["description_keywords"] for kw in keywords):
                    relevant["successful_commands"].append(pattern["command"])
        
        # Find relevant failed patterns to avoid
        for pattern in self.persistent_memory["failed_patterns"]:
            if pattern["action_type"] == action_type:
                relevant["failed_commands"].append(pattern["command"])
        
        return relevant
    
    def complete_task(self, final_result: str, success: bool = True):
        """Mark current task as completed."""
        if self.current_execution:
            self.current_execution.final_result = final_result
            self.current_execution.status = "completed" if success else "failed"
            
            # Save to persistent history
            task_summary = {
                "task_id": self.current_execution.task_id,
                "query": self.current_execution.original_query,
                "success": success,
                "steps_count": len(self.current_execution.steps),
                "completed_at": datetime.now().isoformat()
            }
            
            self.persistent_memory["task_history"].append(task_summary)
            self._save_persistent_memory()
    
    def get_execution_context(self) -> str:
        """Get current execution context as string for LLM."""
        if not self.current_execution:
            return "No current task execution."
        
        context = [
            f"Current Task: {self.current_execution.original_query}",
            f"Status: {self.current_execution.status}",
        ]
        
        if self.current_execution.research_phase:
            context.append(f"Research: {self.current_execution.research_phase[:200]}...")
        
        if self.current_execution.steps:
            context.append("Completed Steps:")
            for step in self.current_execution.steps[-3:]:  # Last 3 steps
                status = "✅" if step.success else "❌"
                context.append(f"  {status} {step.description}")
        
        return "\n".join(context)

# Global memory instance
execution_memory = ExecutionMemory()
