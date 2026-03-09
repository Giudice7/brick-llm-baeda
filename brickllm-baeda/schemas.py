from pydantic import BaseModel, Field
from typing import List


class IdentifiedEntities(BaseModel):
    selected_classes: List[str] = Field(
        description="The final, most specific URIs chosen to represent the objects identified in the user prompt."
    )


class IdentifiedProperties(BaseModel):
    selected_properties: List[str] = Field(
        description="The final list of URIs representing the data properties identified in the user prompt. Returns an empty list if none are found."
    )


class Triple(BaseModel):
    subject: str = Field(description="The URI of the subject entity.")
    predicate: str = Field(description="The URI of the relationship predicate.")
    object: str = Field(description="The URI of the object entity.")


class ExtractedTriples(BaseModel):
    triples: List[Triple] = Field(description="The final list of extracted RDF triples.")
