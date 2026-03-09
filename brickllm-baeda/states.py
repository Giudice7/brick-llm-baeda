import operator
from typing import TypedDict, Annotated

from schemas import IdentifiedEntities, IdentifiedProperties


class WorkflowState(TypedDict, total=False):
    user_input: str
    ontology_name: str
    uri: str

    user_instructions_entity_extractor: str
    identified_entities: IdentifiedEntities
    input_tokens_entity_extractor: int
    output_tokens_entity_extractor: int

    user_instructions_property_extractor: str
    identified_properties: IdentifiedProperties
    input_tokens_property_extractor: int
    output_tokens_property_extractor: int

    user_instructions_relationship_extractor: str
    rdf_graphs: Annotated[list, operator.add]
    input_tokens_knowledge_graph_development: int
    output_tokens_knowledge_graph_development: int
    supported_relationships: dict

    is_valid: bool
    iteration: int
    validation_errors: Annotated[list, operator.add]
    inferred_graph: Annotated[list, operator.add]

    input_tokens_knowledge_graph_refactoring: Annotated[int, operator.add]
    output_tokens_knowledge_graph_refactoring: Annotated[int, operator.add]