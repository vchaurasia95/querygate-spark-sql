import datetime
from zoneinfo import ZoneInfo
from google.adk.agents import LlmAgent

from .requirements import error_interpreter
from .custom_agent.coordinator_agent import CoordinatorAgent
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.adk.events import Event
from pydantic import BaseModel, Field
import logging
from google.genai import types
from vertexai.generative_models import GenerationConfig
from google.adk.models.google_llm import Gemini

from .requirements import model_validator

validation_generation_config = GenerationConfig(
    temperature=0.0,             # For strict, deterministic output
    top_p=0.9,                   # To reduce randomness
    top_k=1,                     # To further reduce randomness
    response_mime_type='application/json' # Crucial for enforcing JSON
)

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)




APP_NAME = "sql_validator_app"
USER_ID = "12345"
SESSION_ID = "123344"


model_validator_agent = LlmAgent(
    name="ModelBasedValidatorAgent",
    model="gemini-2.5-flash",
    instruction=model_validator.MODEL_VALIDATOR_PROMPT,
    description="Strict Spark SQL validator. Returns only structured JSON output. Does not explain, repair, or interpret user queries.",
    output_key="model_agent_result",
    #tools= [validate_sql_syntax],  # Save result to state
    generate_content_config = validation_generation_config,
    # include_contents="none",
)

tool_validator_agent = LlmAgent(
    name="ErrorInterpreterAgent",
    model="gemini-2.5-flash",
    instruction= error_interpreter.ERROR_INTERPRETER_PROMPT,
    description="Strict error interpreter for SQL syntax errors. Analyzes provided SQL query and error message, returning only structured JSON output with clear syntax error explanation.",
    # include_contents="none",
)


coordinator_agent = CoordinatorAgent(
    name="CoordinatorAgent",
    model_validator_agent=model_validator_agent,
    tool_validator_agent=tool_validator_agent,
    sub_agents=[model_validator_agent, tool_validator_agent],
)

# --- Setup Runner and Session ---
session_service = InMemorySessionService()
initial_state = {"input": "Select * from abc;"}
session = session_service.create_session(
    app_name=APP_NAME,
    user_id=USER_ID,
    session_id=SESSION_ID,
    state=initial_state # Pass initial state here
)

runner = Runner(
    agent=coordinator_agent, # Pass the custom orchestrator agent
    app_name=APP_NAME,
    session_service=session_service
)


# --- Function to Interact with the Agent ---
async def call_agent(user_input_topic: str):
    """
    Sends a new topic to the agent (overwriting the initial one if needed)
    and runs the workflow.
    """
    current_session = await session_service.get_session(app_name=APP_NAME, 
                                                  user_id=USER_ID, 
                                                  session_id=SESSION_ID)
    if not current_session:
        logger.error("Session not found!")
        return

    current_session.state["input"] = user_input_topic
    logger.info(f"Updated session state input to: {user_input_topic}")

    content = types.Content(role='user', parts=[types.Part(text=f"{user_input_topic}")])
    events = runner.run(user_id=USER_ID, session_id=SESSION_ID, new_message=content)

    final_response = "No final response captured."
    for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            logger.info(f"Potential final response from [{event.author}]: {event.content.parts[0].text}")
            final_response = event.content.parts[0].text

    print("\n--- Agent Interaction Result ---")
    print("Agent Final Response: ", final_response)

    final_session = session_service.get_session(app_name=APP_NAME, 
                                                user_id=USER_ID, 
                                                session_id=SESSION_ID)
    print("Final Session State:")
    import json
    print(json.dumps(final_session.state, indent=2))
    print("-------------------------------\n")

root_agent = coordinator_agent