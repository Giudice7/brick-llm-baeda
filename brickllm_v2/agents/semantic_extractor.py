import os
import json
from typing import List, Dict, Any

from langchain_core.tools import StructuredTool, tool
from langchain_core.tools import create_schema_from_function
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain.agents import create_agent
from langchain.agents.middleware import ToolRetryMiddleware
from loguru import logger

from ..states import WorkflowState
from ..schemas import IdentifiedOntologyConcepts
from ..utils.llms import calculate_token_usage
from ..ontologies import onto_retriever_mapping
from ..agents.entity_extractor import extract_entities_agent
from ..agents.property_extractor import extract_data_properties_agent
from ..agents.relationship_extractor import extract_object_properties_agent


def semantic_extractor(state: WorkflowState, config: RunnableConfig) -> Dict[str, Any]:
    """
    Orchestrates the ontology extraction by managing sub-agents and validating their outputs.
    """
    user_input = state.get("user_input", "")
    ontology_name = state.get("ontology_name", "Brick")
    llm = config.get("configurable", {}).get("model")

    user_instructions = f"""
    When extracting the ontology concepts, follow the instructions provided by the user for the different stages:
    {state.get("user_instructions_entity_extractor", "")}
    {state.get("user_instructions_relationship_extractor", "")}
    {state.get("user_instructions_property_extractor", "")}
    {state.get("user_instructions_kg_development", "")}
    """

    logger.info(f"🧠 Starting Supervisor Orchestration for {ontology_name} mapping")

    # Load ontology description for the prompt context
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ontology_doc_path = os.path.join(base_dir, "ontologies", ontology_name, "ontology.md")

    entity_expert = extract_entities_agent(
        llm=llm,
        ontology_name=ontology_name,
        user_input=user_input,
        user_instructions=state.get("user_instructions_entity_extractor", "")
    )

    object_property_expert = extract_object_properties_agent(
        llm=llm,
        ontology_name=ontology_name,
        user_input=user_input,
        user_instructions=state.get("user_instructions_relationship_extractor", "")
    )

    data_property_expert = extract_data_properties_agent(
        llm=llm,
        ontology_name=ontology_name,
        user_input=user_input,
        user_instructions=state.get("user_instructions_property_extractor", "")
    )

    @tool("extract_entities", description="Delegate instructions to the entity expert. The tool is already aware of the user input and the ontology context, so just ask to extract the relevant entities for the user's request, or precise request if validation is already done once. DO NOT REPEAT USER INPUT. You standard message will be: 'Extract the relevant entities for the user's request'")
    def call_entity_expert(query: str) -> str:
        result = entity_expert.invoke({"messages": [{"role": "user", "content": query}]})
        return result["messages"][-1].content

    @tool("extract_object_properties", description="Delegate instructions to the object property expert. The tool is already aware of the user input and the ontology context, so just ask to extract the relevant object properties for the user's request, or precise request if validation is already done once. DO NOT REPEAT USER INPUT. You standard message will be: 'Extract the relevant entities for the user's request'")
    def call_object_property_expert(query: str) -> str:
        result = object_property_expert.invoke({"messages": [{"role": "user", "content": query}]})
        return result["messages"][-1].content

    @tool("extract_data_properties", description="Delegate instructions to the data property expert. The tool is already aware of the user input and the ontology context, so just ask to extract the relevant data properties for the user's request, or precise request if validation is already done once. DO NOT REPEAT USER INPUT. You standard message will be: 'Extract the relevant entities for the user's request'")
    def call_data_property_expert(query: str) -> str:
        result = data_property_expert.invoke({"messages": [{"role": "user", "content": query}]})
        return result["messages"][-1].content

    supervisor_prompt = f"""
    You are the Chief Ontology Orchestrator for Ontology Mapping. Your objective is to translate user's input into a semantic T-Box (entities and properties/relationships) using the {ontology_name} ontology.
    
    # AVAILABLE EXPERTS:
    You have access to three experts to assist you in this task:
    1. entitiy_expert: Responsible for identifying the most specific URIs for physical objects, spaces, or conceptual nodes starting from ontological concepts.
    2. object_properties_expert: Responsible for identifying the object properties (URIs) that can logically connect the extracted entities.
    3. data_properties_expert: Responsible for identifying the data properties (URIs) that can be used to describe attributes of the extracted entities.
    Each expert might be equipped with tools to expand their search within the ontology.
    
    # ORCHESTRATION WORKFLOW & RULES:
    
    **STEP 1: INITIAL EXTRACTION**
    Immediately delegate the user's input to ALL the experts ONLY ONE TIME per agent. Instruct them to extract all relevant URIs representing the user's request and save them to the shared state. 
    If the request is a natural language request, forward directly to the experts without any rephrasing. If the request is composed by different inputs, such as images and text, be sure to forward all the necessary information to the experts.
    
    **STEP 2: STRUCTURAL VALIDATION**
    Once both experts have completed their extraction the first time, you MUST call the `get_supported_relationship` tool. This tool will cross-reference the extracted URIs against the ontology's strict domain, range, OWL restrictions and SHACL nodes to see how they connect.
    This tool will return a JSON dictionary showing which entities can be connected through which properties. 
    
    **STEP 3: EVALUATION**
    Analyze the JSON dictionary returned by `get_supported_relationship`. Your goal is to ensure the extracted entities can be logically linked to form a cohesive graph.
    Sometimes, the validation might show that some entities cannot be connected with the current properties. 
    In that case you need to evaluate if this is a critical issue that needs to be fixed by going back to the experts or if there is still a way to represent the A-Box with the current information.
    - Check for disconnected islands (e.g., an extracted `Building` and `Sensor` but no connecting property in the state). If it happens, there could be a missing relationship or a wrong entity extraction.
    - Do not overfit or demand absolute specificity. The goal is to build a flexible schema for unstructured data extraction later. If general topological, spatial, or functional links exist that works, accept it.
    
    **STEP 4: TARGETED REFLECTION (MAXIMUM 2 LOOPS)**
    If the validation JSON shows missing connections, isolated concepts, or missing properties to fulfill the user's prompt:
    - Route back to the specific expert needed to bridge the gap.
    - Provide highly specific, directive feedback based on your evaluation. For example: "The validation shows we cannot connect `ont:Building` to `ont:TemperatureSensor` using the current properties. Please query the ontology for a spatial or containment relationship that bridges them."
    - If an expert explicitly confirms a concept genuinely does not exist in the ontology after thorough searching, accept this limitation to avoid infinite loops.
    
    **STEP 5: FINALIZATION**
    Once the JSON mapping shows a sufficiently connected T-Box representing the user's request, or you reach the 2-loop limit, terminate the process. Return the finalized extraction using the output format provided.
    
    {user_instructions}
    """

    onto_retriever = onto_retriever_mapping[ontology_name]

    check_supported_relationships_tool = StructuredTool(
        name="CheckSupportedRelationships",
        func=onto_retriever.get_supported_relationships,
        description="Evaluates the provided URIs and returns a JSON dictionary showing how they can legally connect according to the ontology.",
        args_schema=create_schema_from_function(func=onto_retriever.get_supported_relationships,
                                                model_name="CheckSupportedRelationshipsSchema", parse_docstring=True))


    def on_failure_func(Exception):
        return "Reached the maximum number of retries for the experts. Continue the workflow with the current information and finalize the output. Do not call this expert again."

    middleware_experts = ToolRetryMiddleware(
        tools=[call_entity_expert, call_object_property_expert, call_data_property_expert, check_supported_relationships_tool],
        max_retries=2,
        on_failure=on_failure_func
    )


    supervisor = create_agent(
        model=llm,
        system_prompt=supervisor_prompt,
        tools=[check_supported_relationships_tool, call_entity_expert, call_object_property_expert, call_data_property_expert],
        middleware=[middleware_experts],
        response_format=IdentifiedOntologyConcepts
    )

    messages_history = [HumanMessage(content=user_input)]
    for event in supervisor.stream(input={"messages": [{"role": "user", "content": user_input}]},
                            config=config, stream_mode="updates"):

        for node_name, node_output in event.items():
            print(f"--- 🔄 Update from node: {node_name} ---")

            if node_output:

                if "messages" in node_output:
                    new_messages = node_output["messages"]

                    if isinstance(new_messages, list):
                        messages_history.extend(new_messages)
                        for msg in new_messages:
                            msg.pretty_print()
                        last_msg = new_messages[-1]
                    else:
                        messages_history.append(new_messages)
                        last_msg = new_messages

                    if last_msg.type == "ai":
                        final_message = last_msg.content


    parsed_data = IdentifiedOntologyConcepts.model_validate_json(final_message)
    input_summary, output_summary = calculate_token_usage(messages_history)

    return {
        "identified_entities": parsed_data.selected_classes,
        "identified_relationships": parsed_data.selected_object_properties,
        "identified_properties": parsed_data.selected_data_properties,
        "input_token_details": [input_summary],
        "output_token_details": [output_summary],

    }

