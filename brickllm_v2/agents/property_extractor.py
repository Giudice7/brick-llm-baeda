import os
import json

from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph.state import CompiledStateGraph
from loguru import logger

from ..schemas import IdentifiedProperties


def extract_data_properties_agent(llm: BaseChatModel, ontology_name: str, user_input: str, user_instructions: str = "") -> CompiledStateGraph:
    if len(user_instructions) > 0:
        user_instructions = f"# USER INSTRUCTIONS:\n{user_instructions}\n\n"
    else:
        user_instructions = ""

    logger.info(f"📏 Extracting {ontology_name} data properties from the user prompt")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    properties_path = os.path.join(base_dir, "ontologies", ontology_name, "properties.json")

    try:
        with open(properties_path, "r", encoding="utf-8") as f:
            available_properties = json.load(f)
    except FileNotFoundError:
        available_properties = {}

    ontology_doc_path = os.path.join(base_dir, "ontologies", ontology_name, "ontology.md")
    try:
        with open(ontology_doc_path, "r", encoding="utf-8") as f:
            ontology_description = f.read()
            ontology_description_text = f"{ontology_description}"
    except FileNotFoundError:
        ontology_description_text = ""

    system_message = f"""
    You are an ontology mapping agent. Your task is to identify the data properties described in the user input that matches the ones provided by an ontology. The ontology you are working with is {ontology_name}.

    {ontology_description_text}

    Here is the complete dictionary of available properties and their descriptions:
    {json.dumps(available_properties, indent=2)}

    # GENERAL INSTRUCTIONS:
    Analyze the user's text carefully. If the user mentions or implies any of these properties, select the corresponding URI.
    
    # USER INPUT:
    {user_input}
    
    {user_instructions}

    Return the result as a structured output matching the IdentifiedProperties schema. 
    """

    summary_middleware = SummarizationMiddleware(
        model=llm,
        trigger=[("messages", 5), ("tokens", 10000)],
        keep=("messages", 5)
    )


    agent = create_agent(
        name="data_property_expert",
        model=llm,
        tools=[],
        middleware=[summary_middleware],
        system_prompt=SystemMessage(content=system_message),
        response_format=IdentifiedProperties
    )

    return agent

    # response = agent.invoke({"messages": [HumanMessage(content=user_input)]})
    #
    # messages = response["messages"]
    #
    # final_message = response["messages"][-1].content
    # input_tokens, output_tokens = calculate_token_usage(messages)
    #
    # try:
    #     parsed_properties = IdentifiedProperties.model_validate_json(final_message)
    #     logger.debug(f"Parsed properties: {parsed_properties.selected_properties}")
    # except Exception:
    #     raise ValueError(f"Failed to parse the agent's response. Response content: {final_message}")
    #
    # return {
    #     "identified_properties": parsed_properties,
    #     "input_token_details": [input_tokens],
    #     "output_token_details": [output_tokens],
    # }
