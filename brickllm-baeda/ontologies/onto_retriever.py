import os
import inspect
import rdflib
import json
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class OntoRetriever(ABC):
    def __init__(self) -> None:
        child_file_path = inspect.getfile(self.__class__)
        self.ontology_dir = os.path.dirname(child_file_path)
        ontology_path = os.path.join(self.ontology_dir, "ontology.ttl")

        self.g = rdflib.Graph()
        self.g.parse(ontology_path, format="turtle")

    def obtain_artifacts(self) -> None:
        """
        Executes the extraction methods and saves the artifacts as JSON files
        in the specific ontology's folder.
        """
        hierarchy = self.get_hierarchy()
        data_properties = self.get_data_properties()
        object_properties = self.get_object_properties()

        hierarchy_path = os.path.join(self.ontology_dir, "hierarchy.json")
        with open(hierarchy_path, "w", encoding="utf-8") as f:
            json.dump(hierarchy, f, indent=4, ensure_ascii=False)

        properties_path = os.path.join(self.ontology_dir, "properties.json")
        with open(properties_path, "w", encoding="utf-8") as f:
            json.dump(data_properties, f, indent=4, ensure_ascii=False)

        relationships_path = os.path.join(self.ontology_dir, "relationships.json")
        with open(relationships_path, "w", encoding="utf-8") as f:
            json.dump(object_properties, f, indent=4, ensure_ascii=False)

    @abstractmethod
    def get_hierarchy(self) -> Dict[str, Dict[str, Any]]:
        """
        Extracts the class hierarchy from the ontology.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where the key is the class URI, and the value is a dictionary
            containing 'children' (List[str]) and 'description' (str).
        """
        pass

    @abstractmethod
    def get_data_properties(self) -> Dict[str, Dict[str, Any]]:
        """
        Extracts the datatype properties from the ontology including their constraints.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where the key is the property URI, and the value is a dictionary
            containing 'description' (str), 'subjects' (List[str]), and 'targets' (List[str] representing datatypes).
        """
        pass

    @abstractmethod
    def get_object_properties(self) -> Dict[str, Dict[str, Any]]:
        """
        Extracts the object properties from the ontology including their constraints.

        Returns:
            Dict[str, Dict[str, Any]]: A dictionary where the key is the property URI, and the value is a dictionary
            containing 'description' (str), 'subjects' (List[str]), and 'targets' (List[str]).
        """
        pass

    @abstractmethod
    def get_supported_relationships(self, entities: List[str], relationships: List[str], properties: List[str]) -> Dict[
        str, Dict[str, List[str]]]:
        """
        Validates and maps supported relationships for a specific subset of entities.

        Args:
            entities (List[str]): Entity URIs extracted by the agent.
            relationships (List[str]): Relationship URIs extracted by the agent.

        Returns:
            Dict[str, Dict[str, List[str]]]: A dictionary mapping a subject URI to its valid relationship URIs,
            which in turn map to a list of valid target URIs from the provided entities list.
        """
        pass