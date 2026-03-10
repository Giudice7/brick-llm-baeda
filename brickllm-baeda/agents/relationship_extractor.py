import os
import json

from loguru import logger
from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from states import WorkflowState
from schemas import IdentifiedRelationships
from utils.llms import calculate_token_usage


def extract_relationships_agent(state: WorkflowState, config: RunnableConfig) -> WorkflowState:
    user_input = state.get("user_input", "")
    ontology_name = state.get("ontology_name", "Brick")
    user_instructions = state.get("user_instructions_relationship_extractor", "")

    logger.info(f"🔗 Extracting {ontology_name} relationships from the user prompt")

    if len(user_instructions) > 0:
        user_instructions = f"#USER INSTRUCTIONS:\n{user_instructions}\n\n"
    else:
        user_instructions = ""

    llm = config.get("configurable", {}).get("model")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    relationships_path = os.path.join(base_dir, "ontologies", ontology_name, "relationships.json")

    try:
        with open(relationships_path, "r", encoding="utf-8") as f:
            available_relationships = json.load(f)
    except FileNotFoundError:
        available_relationships = {}

    system_message = f"""
    You are an ontology mapping agent. Your task is to identify the object properties (relationships) described in the user input that matches the ones provided by an ontology. The ontology you are working with is {ontology_name}.

    Here is the complete dictionary of available relationships and their descriptions:
    {json.dumps(available_relationships, indent=2)}

    # GENERAL INSTRUCTIONS:
    Analyze the user's text carefully. If the user mentions or implies any of these relationships, select the corresponding URI.
    {user_instructions}
    Return the result as a structured output in the format specified by the IdentifiedRelationships schema, with the key "selected_relationships" containing a list of the final URIs you have identified.
    """

    agent = create_agent(
        model=llm,
        tools=[],
        system_prompt=SystemMessage(content=system_message),
        response_format=IdentifiedRelationships
    )

    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    messages = response["messages"]

    final_message = response["messages"][-1].content
    input_tokens, output_tokens = calculate_token_usage(messages)

    try:
        parsed_relationships = IdentifiedRelationships.model_validate_json(final_message)
        logger.debug(f"Parsed relationships: {parsed_relationships.selected_relationships}")
    except Exception:
        raise ValueError(f"Failed to parse the agent's response. Response content: {final_message}")

    return {
        "identified_relationships": parsed_relationships,
        "input_token_details": [input_tokens],
        "output_token_details": [output_tokens],
    }