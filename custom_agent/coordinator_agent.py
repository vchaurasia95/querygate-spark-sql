from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
import json
from typing import AsyncGenerator
from pydantic import Field
from google.genai import types
from ..tools.syntax_validator import validate_sql_syntax

class CoordinatorAgent(BaseAgent):
    """
    Custom agent for a sql validation workflow.

    This agent orchestrates a sequence of LLM agents to perform syntax validation on sql query.
    """

    # # --- Field Declarations for Pydantic ---
    # # Declare the agents passed during initialization as class attributes with type hints
    model_validator_agent: LlmAgent = Field(...)
    error_intepreter_agent: LlmAgent = Field(...)

    # model_config allows setting Pydantic configurations if needed, e.g., arbitrary_types_allowed
    model_config = {"arbitrary_types_allowed": True}
    

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """
        Implements the custom orchestration logic for the sql validation.
        Uses the instance attributes assigned by Pydantic (e.g., self.model_validator_agent).
        """
        # Ensure session state is initialized
        print("-----------------------------Session Start---------------------------------")
        print("Session state:", ctx.session.state)
        print("Context:", ctx.user_content)
        sql_query = ctx.user_content.parts[0].text
        print(sql_query)
        if not sql_query:
            yield Event.text("No SQL input found in session state under key 'input'.")
            return
        
        print(sql_query)
        ctx.session.state.clear() 
        output = validate_sql_syntax(sql_query)
        yield Event(
            author=self.name,
            content=types.Content(
            role="assistant",
            parts=[types.Part(text=f"Tool Validation Result:\n```json\n{json.dumps(output, indent=2)}\n```")]
        ),
            partial=True)
        ctx.session.state["sql_to_validate"] = sql_query

        if output["valid"] and output["valid"] is True:
            ctx.session.state["error"] = ""
            ctx.session.state["model_agent_result"] = "" 
            yield Event(
                author=self.name,
                content=types.Content(
                    role="assistant",
                    parts=[types.Part(text="SQL syntax is valid according to tool. Proceeding with model validation...")]
                ),
                partial=True
            ) 
            async for event in self.model_validator_agent.run_async(ctx):
                yield event
        else:            
            ctx.session.state["error"] = output["message"]
            ctx.session.state["model_agent_result"] = ""
            yield Event(
                author=self.name,
                content=types.Content(
                    role="assistant",
                    parts=[types.Part(text="SQL syntax is invalid according to tool. Proceeding with error interpretion")]
                ),
                partial=True
            )
            print("State after error:", ctx.session.state)
            async for event in self.error_intepreter_agent.run_async(ctx):
                yield event

         # After tool_validator_agent finishes, clear its specific state if needed
        if "error" in ctx.session.state:
            del ctx.session.state["error"]
        if "sql_to_validate" in ctx.session.state:
            del ctx.session.state["sql_to_validate"] # Clear once it's been handled
        if "model_agent_result" in ctx.session.state:
            del ctx.session.state["model_agent_result"]