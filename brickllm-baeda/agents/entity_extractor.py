import os
import json
from typing import Dict
from dotenv import load_dotenv

from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langchain_core.tools import create_schema_from_function
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from loguru import logger

from states import WorkflowState
from schemas import IdentifiedEntities
from tools.hierarchy import retrieve_subclasses
from utils.artifacts import get_initial_state
from utils.llms import calculate_token_usage


def extract_entities_agent(state: WorkflowState, config: RunnableConfig) -> WorkflowState:
    """
    Orchestrates the entity extraction using the provided state and configuration.

    Args:
        state (Dict[str, Any]): The state dictionary containing the user input and ontology details.
        config (Dict[str, Any]): The config dictionary containing the model.

    Returns:
        Dict[str, Any]: A dictionary containing the final parsed entities.
    """

    user_input = state.get("user_input", "")
    ontology_name = state.get("ontology_name", "Brick")
    user_instructions = state.get("user_instructions_entity_extractor", "")
    llm = config.get("configurable", {}).get("model")

    if len(user_instructions) > 0:
        user_instructions = f"# USER INSTRUCTIONS:\n{user_instructions}\n\n"
    else:
        user_instructions = ""

    logger.info(f"🔍 Extracting {ontology_name} entities from the user prompt")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hierarchy_path = os.path.join(base_dir, "ontologies", ontology_name, "hierarchy.json")

    with open(hierarchy_path, "r") as f:
        hierarchy = json.load(f)

    initial_hierarchy_state = get_initial_state(ontology_name, hierarchy, max_depth=2)

    system_message = f"""
    You are an ontology mapping agent. Your task is to identify the most specific URIs for the entities described in the user input. The ontology you are working with is {ontology_name}.

    You have this initial hierarchy starting from the main entities:
    {json.dumps(initial_hierarchy_state)}
    
    # GENERAL INSTRUCTIONS:
    If a term in your current hierarchy matches the user's entity but might be too broad, use the ExpandOntologyNode tool to retrieve its children and choose the proper class.
    Stop exploring a branch when you find the best matching term, or when the tool returns an empty list. To be sure, expand always one more time after finding a match, to check if there are more specific subclasses.
    
    {user_instructions}
    
    Once you have finished exploring and have your final list, return the result as a structured output in the format specified by the IdentifiedEntities schema, with the key "selected_classes" containing a list of the final URIs you have identified as the best matches for the entities in the user input.
    """

    node_expansion_tool = StructuredTool(
        name="ExpandOntologyNode",
        func=retrieve_subclasses,
        description="Retrieves the subclasses for given URIs up to a depth of 2. Useful when a matched entity is too broad and more specific subclasses need to be evaluated.",
        args_schema=create_schema_from_function(func=retrieve_subclasses, model_name="ExpandOntologyNodeSchema",
                                                parse_docstring=True)
    )

    agent = create_agent(
        model=llm,
        tools=[node_expansion_tool],
        system_prompt=SystemMessage(content=system_message),
        response_format=IdentifiedEntities
    )

    response = agent.invoke({"messages": [HumanMessage(content=f"Find the ontological entities of the following input: {user_input}")]})

    messages = response["messages"]
    final_message = response["messages"][-1].content
    input_tokens, output_tokens = calculate_token_usage(messages)

    try:
        parsed_entities = IdentifiedEntities.model_validate_json(final_message)
        logger.debug(f"Parsed entities: {parsed_entities.selected_classes}")
    except Exception:
        raise ValueError(f"Failed to parse the agent's response. Response content: {final_message}")

    return {
        "identified_entities": parsed_entities,
        "input_token_details": [input_tokens],
        "output_token_details": [output_tokens],
    }
