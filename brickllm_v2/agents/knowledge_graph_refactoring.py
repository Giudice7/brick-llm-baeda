import os
import json

import rdflib
from loguru import logger
from langchain.agents import create_agent
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from ..states import WorkflowState
from ..schemas import IdentifiedProperties, IdentifiedEntities, IdentifiedRelationships
from ..utils.llms import calculate_token_usage
from ..utils.validation import fix_malformed_literals
from ..tools.graph_editor import add_triple, delete_triple
from ..ontologies import onto_retriever_mapping


def knowledge_graph_refactoring_agent(state: WorkflowState, config: RunnableConfig) -> WorkflowState:
    graph = state.get("rdf_graphs", [])[-1]
    validation_errors_list = state.get("validation_errors", [])
    ontology_name = state.get("ontology_name", "Brick")
    uri = state.get("uri", "https://example.com/building#")

    logger.info(f"🛠️ Refactoring knowledge graph to resolve {ontology_name} validation errors")

    current_errors = validation_errors_list[-1] if validation_errors_list else {}
    llm = config.get("configurable", {}).get("model")

    identified_entities = state.get("identified_entities", [])
    if isinstance(identified_entities, IdentifiedEntities):
        identified_entities = identified_entities.selected_classes
    identified_properties = state.get("identified_properties", [])
    if isinstance(identified_properties, IdentifiedProperties):
        identified_properties = identified_properties.selected_properties
    identified_relationships = state.get("identified_relationships", [])
    if isinstance(identified_relationships, IdentifiedRelationships):
        identified_relationships = identified_relationships.selected_relationships

    onto_retriever = onto_retriever_mapping[ontology_name]

    supported_relationships = state.get("supported_relationships", onto_retriever.get_supported_relationships(
        identified_entities,
        identified_relationships,
        identified_properties))

    add_tool = StructuredTool.from_function(
        func=lambda subject_uri, predicate_uri, object_value, is_literal: add_triple(
            graph=graph,
            subject_uri=subject_uri,
            predicate_uri=predicate_uri,
            object_value=object_value,
            is_literal=is_literal
        ),
        name="add_triple",
        description="Adds a new triple to the knowledge graph to fix ontological violations."
    )

    delete_tool = StructuredTool.from_function(
        func=lambda subject_uri, predicate_uri, object_value, is_literal: delete_triple(
            graph=graph,
            subject_uri=subject_uri,
            predicate_uri=predicate_uri,
            object_value=object_value,
            is_literal=is_literal
        ),
        name="delete_triple",
        description="Deletes an existing triple from the knowledge graph to resolve conflicts."
    )

    system_message = f"""
        You are an ontology-based Knowledge Graph Refactoring agent. Your task is to resolve SHACL validation errors for an existing ontology-based RDF graph.
        The ontology you are working with is {ontology_name}.
        The base namespace for this graph is {uri}.

        Here are the specific ontology classes identified from other agents in the text:
        {json.dumps(identified_entities, indent=2)}

        Here are the properties identified from other agents in the text:
        {json.dumps(identified_properties, indent=2)}
               
        Here are the relationships identified in the text:
        {json.dumps(identified_relationships, indent=2)}
        
        Here is the context dictionary mapping the identified entities to their ALLOWED structural relationships and data properties:
        ## CONTEXT DICTIONARY:
        {json.dumps(supported_relationships, indent=2)}
        
        A snapshot of the current graph in Turtle format is provided:
        {graph.serialize(format="turtle")}
        
        Your job is to:
        1. Review the SHACL validation errors provided in the user message.
        3. Use the `add_triple` and `delete_triple` tools to fix the graph so it conforms to the ontology.
        4. Do not invent properties or classes, always use the information provided into the context dictionary and the current graph snapshot to make your decisions.
        
        # IMPORTANT RULE:
        When an error says that a certain value is not of a specific class, the solution usually is not to add the class type as stated in the error message,  but to change the subject or object entity type, or that the two entities in the triple are not connected by the correct property. Always analyze the error deeply and check the supported rules before making changes.
        """

    agent = create_agent(
        model=llm,
        tools=[add_tool, delete_tool],
        system_prompt=SystemMessage(content=system_message),
        response_format=None
    )

    user_input = f"Fix the following SHACL validation errors:\n{json.dumps(current_errors, indent=2)}"
    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    messages = response["messages"]
    final_message = response["messages"][-1].content
    input_tokens, output_tokens = calculate_token_usage(messages)
    logger.debug(f"Knowledge Graph Refactoring Agent response: {final_message}")

    return {
        "rdf_graphs": [fix_malformed_literals(graph)],
        "input_token_details": [input_tokens],
        "output_token_details": [output_tokens]
    }
