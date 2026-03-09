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


import rdflib
from rdflib.namespace import RDF, RDFS, Namespace
import json

SH = Namespace("http://www.w3.org/ns/shacl#")

IGNORED_CLASSES = {
    rdflib.URIRef("https://brickschema.org/schema/Brick#Entity"),
    rdflib.URIRef("http://www.w3.org/2000/01/rdf-schema#Resource"),
    rdflib.URIRef("http://www.w3.org/2002/07/owl#Thing")
}

import rdflib
from rdflib.namespace import RDF, RDFS, Namespace
import json

SH = Namespace("http://www.w3.org/ns/shacl#")

IGNORED_CLASSES = {
    rdflib.URIRef("https://brickschema.org/schema/Brick#Entity"),
    rdflib.URIRef("http://www.w3.org/2000/01/rdf-schema#Resource"),
    rdflib.URIRef("http://www.w3.org/2002/07/owl#Thing")
}


def get_supported_relationships(identified_entities, identified_relationships, g):
    superclasses_cache = {}

    def fetch_superclasses(entity_uri):
        if entity_uri in superclasses_cache:
            return superclasses_cache[entity_uri]

        supers = set()
        stack = [entity_uri]

        while stack:
            current = stack.pop()
            if current not in supers:
                supers.add(current)
                for parent in g.objects(current, RDFS.subClassOf):
                    if isinstance(parent, rdflib.URIRef):
                        stack.append(parent)

        superclasses_cache[entity_uri] = supers
        return supers

    entity_superclasses = {}
    allowed_paths = set(identified_relationships)

    for ent in identified_entities:
        ent_uri = rdflib.URIRef(ent)
        entity_superclasses[ent_uri] = fetch_superclasses(ent_uri)

    supported = {}

    for ent_uri, supers in entity_superclasses.items():
        ent_str = str(ent_uri)
        supported[ent_str] = {}

        for superclass in supers:
            if superclass in IGNORED_CLASSES:
                continue

            for prop_shape in g.objects(superclass, SH.property):
                path = g.value(prop_shape, SH.path)
                if not path:
                    continue

                path_str = str(path)
                if path_str not in allowed_paths:
                    continue

                target_classes = set()
                datatypes = set()
                node_kinds = set()

                for sh_class in g.objects(prop_shape, SH["class"]):
                    if sh_class not in IGNORED_CLASSES:
                        target_classes.add(sh_class)
                for sh_node in g.objects(prop_shape, SH.node):
                    if sh_node not in IGNORED_CLASSES:
                        target_classes.add(sh_node)
                for dt in g.objects(prop_shape, SH.datatype):
                    datatypes.add(dt)
                for nk in g.objects(prop_shape, SH.nodeKind):
                    node_kinds.add(nk)

                or_list = g.value(prop_shape, SH["or"])
                if or_list:
                    current_node = or_list
                    while current_node and current_node != RDF.nil:
                        first = g.value(current_node, RDF.first)
                        if first:
                            for sh_class in g.objects(first, SH["class"]):
                                if sh_class not in IGNORED_CLASSES:
                                    target_classes.add(sh_class)
                            for sh_node in g.objects(first, SH.node):
                                if sh_node not in IGNORED_CLASSES:
                                    target_classes.add(sh_node)
                            for dt in g.objects(first, SH.datatype):
                                datatypes.add(dt)
                            for nk in g.objects(first, SH.nodeKind):
                                node_kinds.add(nk)
                        current_node = g.value(current_node, RDF.rest)

                resolved_targets = set()

                for target_class in target_classes:
                    resolved_targets.add(str(target_class))
                    for ident_ent, ident_supers in entity_superclasses.items():
                        if target_class in ident_supers:
                            resolved_targets.add(str(ident_ent))

                for dt in datatypes:
                    resolved_targets.add(str(dt))

                for nk in node_kinds:
                    if nk != SH.IRI and nk != SH.BlankNode:
                        resolved_targets.add(str(nk))

                if not resolved_targets:
                    resolved_targets.add("http://www.w3.org/2000/01/rdf-schema#Resource")

                if resolved_targets:
                    if path_str not in supported[ent_str]:
                        supported[ent_str][path_str] = []
                    for target in resolved_targets:
                        if target != ent_str and target not in supported[ent_str][path_str]:
                            supported[ent_str][path_str].append(target)

    for ent in supported:
        for path in supported[ent]:
            supported[ent][path] = sorted(supported[ent][path])

    return supported


if __name__ == "__main__":
    ontology_graph = rdflib.Graph()
    try:
        ontology_graph.parse("../ontologies/Brick/ontology.ttl", format="turtle")
    except Exception:
        pass

    entities_from_llm = ['https://w3id.org/rec#Building', 'https://w3id.org/rec#Zone',
                         'https://brickschema.org/schema/Brick#Air_Handling_Unit',
                         'https://brickschema.org/schema/Brick#HVAC_Equipment',
                         'https://brickschema.org/schema/Brick#Cooling_Coil',
                         'https://brickschema.org/schema/Brick#Supply_Fan',
                         'https://brickschema.org/schema/Brick#Return_Fan',
                         'https://brickschema.org/schema/Brick#Outdoor_Air_Damper',
                         'https://brickschema.org/schema/Brick#Return_Air_Damper',
                         'https://brickschema.org/schema/Brick#Zone_Air_Temperature_Sensor',
                         'https://brickschema.org/schema/Brick#Valve_Position_Sensor',
                         'https://brickschema.org/schema/Brick#Damper_Position_Sensor',
                         'https://brickschema.org/schema/Brick#Speed_Setpoint',
                         'https://brickschema.org/schema/Brick#Speed_Status',
                         'https://brickschema.org/schema/Brick#Supply_Air_Temperature_Sensor',
                         'https://brickschema.org/schema/Brick#Return_Air_Temperature_Sensor',
                         'https://brickschema.org/schema/Brick#Outside_Air_Temperature_Sensor',
                         'https://brickschema.org/schema/Brick#Mixed_Air_Temperature_Sensor',
                         'https://brickschema.org/schema/Brick#Supply_Air_Temperature_Setpoint',
                         'https://brickschema.org/schema/Brick#Operating_Mode_Status',
                         'https://brickschema.org/schema/Brick#Supply_Air_Flow_Sensor',
                         'https://brickschema.org/schema/Brick#Return_Air_Flow_Sensor',
                         'https://brickschema.org/schema/Brick#Outside_Air_Flow_Sensor',
                         'https://brickschema.org/schema/Brick#Valve']

    relationships_from_llm = ['https://w3id.org/rec#area',
                              'https://brickschema.org/schema/Brick#hasPart',
                              'https://brickschema.org/schema/Brick#isPartOf',
                              'https://brickschema.org/schema/Brick#feeds',
                              'https://brickschema.org/schema/Brick#isFedBy',
                              'https://brickschema.org/schema/Brick#hasPoint',
                              'https://brickschema.org/schema/Brick#isPointOf',
                              'https://brickschema.org/schema/Brick#hasUnit',
                              'https://brickschema.org/schema/Brick#value',
                              'https://brickschema.org/schema/Brick#hasQuantity']

    filtered_relationships = get_supported_relationships(
    entities_from_llm,
    relationships_from_llm,
    ontology_graph
    )

    print(json.dumps(filtered_relationships, indent=4))
