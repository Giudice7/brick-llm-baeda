import operator
from typing import TypedDict, Annotated, List

from .schemas import IdentifiedEntities, IdentifiedProperties, IdentifiedRelationships, InputTokenDetails, OutputTokenDetails


class WorkflowState(TypedDict, total=False):
    user_input: str
    ontology_name: str
    uri: str

    input_token_details: Annotated[List[InputTokenDetails], operator.add]
    output_token_details: Annotated[List[OutputTokenDetails], operator.add]

    user_instructions_entity_extractor: str
    identified_entities: IdentifiedEntities

    user_instructions_property_extractor: str
    identified_properties: IdentifiedProperties

    user_instructions_relationship_extractor: str
    identified_relationships: IdentifiedRelationships

    user_instructions_kg_development: str

    rdf_graphs: Annotated[list, operator.add]

    supported_relationships: dict

    is_valid: bool
    iteration: int
    validation_errors: Annotated[list, operator.add]
    inferred_graph: Annotated[list, operator.add]
