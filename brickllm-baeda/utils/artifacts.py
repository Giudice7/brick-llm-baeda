from typing import List, Dict, Any

from ontologies.utils import get_root_entities


def extract_hierarchy_depth(hierarchy: dict, target_uris: list, max_depth: int, current_depth: int = 1) -> dict:
    """Recursively retrieves a subset of the hierarchy for a list of URIs up to a specified depth.

    Args:
        hierarchy (dict): The complete loaded hierarchy dictionary.
        target_uris (list): A list of starting URIs for the extraction.
        max_depth (int): The maximum depth to traverse.
        current_depth (int, optional): The current depth in the recursion. Defaults to 1.

    Returns:
        dict: A nested dictionary representing the combined hierarchy subset.
    """
    result = {}

    for uri in target_uris:
        if current_depth > max_depth or uri not in hierarchy:
            continue

        node_data = hierarchy[uri]
        node_result = {
            "label": node_data.get("label", ""),
            "description": node_data.get("description", ""),
            "subclasses": {}
        }

        children = node_data.get("children", [])
        if children:
            if current_depth == max_depth:
                for child in children:
                    child_data = hierarchy.get(child, {})
                    node_result["subclasses"][child] = {
                        "label": child_data.get("label", ""),
                        "description": child_data.get("description", "")
                    }
            else:
                node_result["subclasses"] = extract_hierarchy_depth(
                    hierarchy,
                    children,
                    max_depth,
                    current_depth + 1
                )

        result[uri] = node_result

    return result


def get_initial_state(ontology_name: str, hierarchy: dict, max_depth: int) -> dict:
    """Retrieves the initial hierarchy state starting from the root entities.

    Args:
        ontology_name (str): The name of the ontology.
        hierarchy (dict): The complete loaded hierarchy dictionary.
        max_depth (int): The maximum depth to traverse.

    Returns:
        dict: A nested dictionary representing the initial hierarchy state.
    """
    root_uris = get_root_entities(ontology_name)
    return extract_hierarchy_depth(hierarchy, root_uris, max_depth)
