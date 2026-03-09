import os
import json
from typing import Dict, Any, List
from utils.artifacts import extract_hierarchy_depth


def retrieve_subclasses(uris: List[str], ontology_name: str) -> Dict[str, Any]:
    """
    Retrieves the subclasses for a given list of URIs up to a depth of 2. It is advised to not use more than 3 URIs for each call to avoid excessive output.

    Args:
        uris (List[str]): A list of URIs representing the entities to expand.
        ontology_name (str): The name of the ontology folder to search within.

    Returns:
        Dict[str, Any]: A nested dictionary containing the subclasses, labels, and descriptions up to depth 2.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hierarchy_path = os.path.join(base_dir, "ontologies", ontology_name, "hierarchy.json")

    try:
        with open(hierarchy_path, 'r') as f:
            hierarchy = json.load(f)
    except FileNotFoundError:
        return {"error": f"Hierarchy file for {ontology_name} not found."}

    return extract_hierarchy_depth(hierarchy, uris, max_depth=2)