from pydantic import BaseModel, Field
from typing import List
from typing_extensions import TypedDict


class IdentifiedEntities(BaseModel):
    selected_classes: List[str] = Field(
        description="The final, most specific URIs chosen to represent the objects identified in the user prompt."
    )


class IdentifiedProperties(BaseModel):
    selected_properties: List[str] = Field(
        description="The final list of URIs representing the data properties identified in the user prompt. Returns an empty list if none are found."
    )

class IdentifiedRelationships(BaseModel):
    selected_relationships: List[str] = Field(
        description="The final list of URIs representing the object properties (relationships) identified in the user prompt. Returns an empty list if none are found."
    )


class Triple(BaseModel):
    subject: str = Field(description="The URI of the subject entity.")
    predicate: str = Field(description="The URI of the relationship predicate.")
    object: str = Field(description="The URI of the object entity.")


class ExtractedTriples(BaseModel):
    triples: List[Triple] = Field(description="The final list of extracted RDF triples.")


class InputTokenDetails(TypedDict, total=False):
    total_tokens: int
    audio: int
    cache_creation: int
    cache_read: int
    cache_read_over_200k: int
    ephemeral_5m_input_tokens: int
    ephemeral_1h_input_tokens: int

class OutputTokenDetails(TypedDict, total=False):
    total_tokens: int
    audio: int
    reasoning: int