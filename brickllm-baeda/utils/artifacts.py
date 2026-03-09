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


def get_supported_relationships(
    extracted_entities: List[str],
    extracted_properties: List[str],
    hierarchy: Dict[str, Any],
    relationships_rules: Dict[str, Any],
    properties_data: Dict[str, Any]
) -> Dict[str, Any]:
    parent_map = {}
    for parent_uri, node_data in hierarchy.items():
        for child_uri in node_data.get("children", []):
            if child_uri not in parent_map:
                parent_map[child_uri] = []
            parent_map[child_uri].append(parent_uri)

    context = {}

    for entity in extracted_entities:
        queue = [entity]
        visited_ancestors = set()
        proximal_ancestor = None
        inherited_rules = {}

        while queue:
            current = queue.pop(0)
            if current in visited_ancestors:
                continue
            visited_ancestors.add(current)

            if current in relationships_rules:
                if not proximal_ancestor:
                    proximal_ancestor = current

                for path, targets in relationships_rules[current].items():
                    if path not in inherited_rules:
                        inherited_rules[path] = []
                    inherited_rules[path].extend(targets)
                    inherited_rules[path] = list(set(inherited_rules[path]))

            for parent in parent_map.get(current, []):
                queue.append(parent)

        supported_dps = {}
        for dp in extracted_properties:
            for ancestor in visited_ancestors:
                if ancestor in properties_data and dp in properties_data[ancestor]:
                    supported_dps[dp] = properties_data[ancestor][dp]
                    break

        context[entity] = {
            "subClassOf": proximal_ancestor if proximal_ancestor else "Unknown",
            "supported_relationships": inherited_rules,
            "supported_properties": supported_dps
        }

    return context


def get_unique_properties(properties_data: Dict) -> List[str]:
    """
    Extracts a list of unique property URIs from the properties data dictionary extracted from the ontology.
    Args:
        properties_data: Dictionary called property.json containing the properties organized by domain classes.

    Returns:
        list of unique property URIs found in the properties data.
    """

    unique_properties = set()
    for domain_props in properties_data.values():
        for prop_uri in domain_props.keys():
            unique_properties.add(prop_uri)

    return list(unique_properties)
