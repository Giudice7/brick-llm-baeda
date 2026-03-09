import os
import json
from typing import Dict

from loguru import logger
from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from states import WorkflowState
from schemas import IdentifiedProperties
from utils.artifacts import get_unique_properties


def extract_properties_agent(state: WorkflowState, config: RunnableConfig) -> WorkflowState:
    """
    Orchestrates the data property extraction using the provided state and configuration.

    Args:
        state (Dict[str, Any]): The state dictionary containing the user input and ontology details.
        config (Dict[str, Any]): The config dictionary containing the model.

    Returns:
        Dict[str, Any]: A dictionary containing the final parsed data properties and token usage.
    """
    user_input = state.get("user_input", "")
    ontology_name = state.get("ontology_name", "Brick")
    user_instructions = state.get("user_instructions_property_extractor", "")

    logger.info(f"📏 Extracting {ontology_name} properties from the user prompt")

    if len(user_instructions) > 0:
        user_instructions = f"#USER INSTRUCTIONS:\n{user_instructions}\n\n"
    else:
        user_instructions = ""

    llm = config.get("configurable", {}).get("model")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    properties_path = os.path.join(base_dir, "ontologies", ontology_name, "properties.json")

    try:
        with open(properties_path, "r", encoding="utf-8") as f:
            available_properties = json.load(f)
            available_properties = get_unique_properties(available_properties)
    except FileNotFoundError:
        available_properties = {}


    system_message = f"""
    You are an ontology mapping agent. Your task is to identify the data properties described in the user input. The ontology you are working with is {ontology_name}.

    Data properties describe the quantitative or qualitative attributes of an entity, connecting an object to a literal value (e.g., a number, string, or boolean). Examples include a device's 'cooling capacity', 'electrical consumption', or 'maximum limit'. 

    Here is the complete dictionary of available properties, their labels, and descriptions:
    {json.dumps(available_properties, indent=2)}

    # GENERAL INSTRUCTIONS:
    Analyze the user's text carefully. If the user explicitly mentions or clearly implies any of these properties, select the corresponding URI.
    Crucially, if the text does NOT contain any concepts that map to these properties, you MUST return an empty list. Do not force a match if one does not logically exist.

    {user_instructions}

    Once you have finished exploring, return the result as a structured output in the format specified by the IdentifiedDataProperties schema, with the key "selected_properties" containing a list of the final URIs you have identified.
    """

    agent = create_agent(
        model=llm,
        tools=[],
        system_prompt=SystemMessage(content=system_message),
        response_format=IdentifiedProperties
    )

    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    messages = response["messages"]
    input_tokens = 0
    output_tokens = 0
    for message in messages:
        if isinstance(message, AIMessage):
            input_tokens += message.usage_metadata["input_tokens"]
            output_tokens += message.usage_metadata["output_tokens"]

    final_message = response["messages"][-1].content

    try:
        parsed_properties = IdentifiedProperties.model_validate_json(final_message)
        logger.debug(f"Parsed properties: {parsed_properties.selected_properties}")
    except Exception:
        raise ValueError(f"Failed to parse the agent's response. Response content: {final_message}")

    return {
        "identified_properties": parsed_properties,
        "input_tokens_property_extractor": input_tokens,
        "output_tokens_property_extractor": output_tokens,
    }


if __name__ == "__main__":
    from langchain_openai import ChatOpenAI
    from dotenv import load_dotenv

    load_dotenv()

    description = """
    The facility is a small commercial building with a total floor area of 450 square meters. 
    The building's climate is managed by a single Air Handling Unit located on the roof. 
    This Air Handling Unit contains a heating coil that provides a heating capacity of 15 kW 
    and a cooling coil that provides a cooling capacity of 22 kW.
    """

    llm_instance = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0
    )

    test_state = {
        "user_input": description,
        "ontology_name": "Brick",
        "user_instructions_dataproperty_extractor": ""
    }

    test_config = {
        "configurable": {
            "model": llm_instance
        }
    }

    result = extract_properties_agent(test_state, test_config)

    print("Identified Data Properties:")
    for property_uri in result.get("identified_dataproperties", []):
        print(property_uri)

    print(f"\nInput Tokens: {result.get('input_tokens_property_extractor')}")
    print(f"Output Tokens: {result.get('output_tokens_property_extractor')}")