import os
import json

from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import StructuredTool
from langchain_core.tools import create_schema_from_function
from langchain_core.messages import SystemMessage
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from ..schemas import IdentifiedEntities
from ..tools.hierarchy import retrieve_subclasses
from ..utils.artifacts import get_initial_state


def extract_entities_agent(llm: BaseChatModel, ontology_name: str, user_instructions: str = "") -> CompiledStateGraph:
    """
    Orchestrates the entity extraction using the provided state and configuration.

    Args:
        llm: A language model instance to be used by the agent for processing.
        ontology_name: The name of the ontology to be used for entity extraction (e.g., "Brick", "saref", etc.).
        user_instructions: Optional additional instructions to guide the entity extraction process.

    Returns:
        CompiledStateGraph: An agent configured to extract entities based on the specified ontology and user instructions.
    """

    if len(user_instructions) > 0:
        user_instructions = f"# USER INSTRUCTIONS:\n{user_instructions}\n\n"
    else:
        user_instructions = ""

    logger.info(f"🔍 Extracting {ontology_name} entities from the user prompt")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hierarchy_path = os.path.join(base_dir, "ontologies", ontology_name, "hierarchy.json")

    with open(hierarchy_path, "r") as f:
        hierarchy = json.load(f)

    ontology_doc_path = os.path.join(base_dir, "ontologies", ontology_name, "ontology.md")
    try:
        with open(ontology_doc_path, "r", encoding="utf-8") as f:
            ontology_description = f.read()
            ontology_description_text = f"{ontology_description}"
    except FileNotFoundError:
        ontology_description_text = ""

    initial_hierarchy_state = get_initial_state(ontology_name, hierarchy, max_depth=2)

    system_message = f"""
    You are an ontology mapping agent. Your task is to identify the most specific URIs for the entities described in the user input. The ontology you are working with is {ontology_name}.
    
    {ontology_description_text}
    
    You have this initial hierarchy starting from the main entities:
    {json.dumps(initial_hierarchy_state)}
    
    # GENERAL INSTRUCTIONS:
    If a term in your current hierarchy matches the user's entity but might be too broad, use the ExpandOntologyNode tool to retrieve its children and choose the proper class.
    Stop exploring a branch when you find the best matching term, or when the tool returns an empty list. To be sure, expand always one more time after finding a match, to check if there are more specific subclasses.
    
    {user_instructions}
    
    Once you have finished exploring and have your final list, return the result as a structured output matching the IdentifiedEntities schema.
    """

    node_expansion_tool = StructuredTool(
        name="ExpandOntologyNode",
        func=retrieve_subclasses,
        description="Retrieves the subclasses for given URIs up to a depth of 2. Useful when a matched entity is too broad and more specific subclasses need to be evaluated.",
        args_schema=create_schema_from_function(func=retrieve_subclasses, model_name="ExpandOntologyNodeSchema",
                                                parse_docstring=True)
    )

    agent = create_agent(
        name="entity_expert",
        model=llm,
        tools=[node_expansion_tool],
        system_prompt=SystemMessage(content=system_message),
        response_format=IdentifiedEntities
    )

    return agent

    # response = agent.invoke({"messages": [HumanMessage(content=f"Find the ontological entities of the following input: {user_input}")]})
    #
    # messages = response["messages"]
    # final_message = response["messages"][-1].content
    # input_tokens, output_tokens = calculate_token_usage(messages)
    #
    # try:
    #     parsed_entities = IdentifiedEntities.model_validate_json(final_message)
    #     logger.debug(f"Parsed entities: {parsed_entities.selected_classes}")
    # except Exception:
    #     raise ValueError(f"Failed to parse the agent's response. Response content: {final_message}")
    #
    # return {
    #     "identified_entities": parsed_entities,
    #     "input_token_details": [input_tokens],
    #     "output_token_details": [output_tokens],
    # }
