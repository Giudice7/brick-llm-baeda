import os
import json

import rdflib
from loguru import logger
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from ..schemas import ExtractedTriples, IdentifiedEntities, IdentifiedProperties, IdentifiedRelationships
from ..states import WorkflowState
from ..ontologies import onto_retriever_mapping
from ..utils.llms import calculate_token_usage
from ..utils.validation import fix_malformed_literals


def knowledge_graph_agent(state: WorkflowState, config: RunnableConfig) -> WorkflowState:
    user_input = state.get("user_input", "")
    ontology_name = state.get("ontology_name", "Brick")
    identified_entities = state.get("identified_entities", [])
    if isinstance(identified_entities, IdentifiedEntities):
        identified_entities = identified_entities.selected_classes
    identified_properties = state.get("identified_properties", [])
    if isinstance(identified_properties, IdentifiedProperties):
        identified_properties = identified_properties.selected_properties
    identified_relationships = state.get("identified_relationships", [])
    if isinstance(identified_relationships, IdentifiedRelationships):
        identified_relationships = identified_relationships.selected_relationships

    user_instructions = state.get("user_instructions_kg_development", "")
    uri = state.get("uri", "https://example.com/building#")

    logger.info(f"🏗️ Building initial {ontology_name} knowledge graph")

    if len(user_instructions) > 0:
        user_instructions = "# USER INSTRUCTIONS:\n" + user_instructions + "\n\n"
    else:
        user_instructions = ""

    llm = config.get("configurable", {}).get("model")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    onto_retriever = onto_retriever_mapping[ontology_name]

    supported_relationships = onto_retriever.get_supported_relationships(
        identified_entities,
        identified_relationships,
        identified_properties)

    system_message = f"""
        You are an ontology Knowledge Graph building agent. Your task is to instantiate entities from the text and connect them. The ontology you are working with is {ontology_name}.

        Here are the specific ontology classes identified in the text:
        {json.dumps(identified_entities, indent=2)}

        Here are the properties identified in the text:
        {json.dumps(identified_properties, indent=2)}
        
        Here are the relationships identified in the text:
        {json.dumps(identified_relationships, indent=2)}

        Here is the context dictionary mapping the identified entities to their ALLOWED structural relationships and properties:
        {json.dumps(supported_relationships, indent=2)}

        # GENERAL INSTRUCTIONS:
        1. INSTANTIATE: For every physical object or concept mentioned in the text, create a unique instance URI using this base namespace: {uri} (e.g., {uri}ahu_1, {uri}room_A).
        2. ASSIGN TYPE: For each instance you create, you MUST assign it a class from the identified list using the predicate "http://www.w3.org/1999/02/22-rdf-syntax-ns#type". 
           Example: [ {uri}ahu_1, http://www.w3.org/1999/02/22-rdf-syntax-ns#type, https://brickschema.org/schema/Brick#Air_Handling_Unit ]

        3. CONNECT INSTANCES: Connect the physical instances to each other based on the input provided by the user. 
           CRITICAL: When connecting instance A to instance B, look up the supported relationships for instance A's class in the dictionary above. Do not invent predicates.
           You MUST follow these two exact patterns:
           - DIRECT PATTERN: valid for both object properties that connect two nodes or data properties that connect a node to a literal value.
            For the latter, if the property in the dictionary maps to a flat list (e.g., ["http://www.w3.org/2001/XMLSchema#string"]), connect the main instance directly to the literal value, specifying the XML schema type (e.g. "anykindoftext"^^http://www.w3.org/2001/XMLSchema#string.
             Example: [ {uri}sensor_1, https://brickschema.org/schema/Brick/ref#hasTimeseriesId, "abc-123"^^http://www.w3.org/2001/XMLSchema#string ]
           - COMPLEX PATTERN (SHAPE/NODE): If the property in the dictionary maps to a nested dictionary (e.g., containing "value" and "hasUnit"), DO NOT assign the literal directly to the main instance. Instead:
             a) Create a new unique URI for this property node (e.g., {uri}room_A_area).
             b) Connect the main instance to this new node using the main property predicate.
             c) Connect the new node to the numeric value and its unit using the nested predicates provided in the dictionary.
             Example for an Area of 100 M2:
             [ {uri}room_A, https://brickschema.org/schema/Brick#area, {uri}room_A_area ]
             [ {uri}room_A_area, https://brickschema.org/schema/Brick#value, "100"^^http://www.w3.org/2001/XMLSchema#integer ]
             [ {uri}room_A_area, https://brickschema.org/schema/Brick#hasUnit, http://qudt.org/vocab/unit/M2 ]

        {user_instructions}

        Return a list of triples representing the final knowledge graph in the format specified by the ExtractedTriples schema.
        """

    agent = create_agent(
        model=llm,
        tools=[],
        system_prompt=SystemMessage(content=system_message),
        response_format=ExtractedTriples
    )

    response = agent.invoke({"messages": [HumanMessage(content=user_input)]})

    messages = response["messages"]
    final_message = response["messages"][-1].content
    input_tokens, output_tokens = calculate_token_usage(messages)

    try:
        parsed_data = ExtractedTriples.model_validate_json(final_message)
    except Exception:
        raise ValueError(f"Failed to parse the agent's response. Response content: {final_message}")

    namespaces_path = os.path.join(base_dir, "ontologies", "namespaces.json")
    with open(namespaces_path, "r", encoding="utf-8") as f:
        ontology_namespaces = json.load(f)

    g = rdflib.Graph()

    for prefix, namespace_uri in ontology_namespaces.items():
        g.bind(prefix, rdflib.Namespace(namespace_uri))

    g.bind("bldg", rdflib.Namespace(uri))

    for triple in parsed_data.triples:
        subject_node = rdflib.URIRef(triple.subject)
        predicate_node = rdflib.URIRef(triple.predicate)

        if str(triple.object).startswith("http"):
            object_node = rdflib.URIRef(triple.object)
        else:
            object_node = rdflib.Literal(triple.object)

        g.add((subject_node, predicate_node, object_node))

    logger.debug(f"RDF graph generated:\n{g.serialize(format='turtle')}")

    return {
        "rdf_graphs": [fix_malformed_literals(g)],
        "input_token_details": [input_tokens],
        "output_token_details": [output_tokens],
        "supported_relationships": supported_relationships
    }
