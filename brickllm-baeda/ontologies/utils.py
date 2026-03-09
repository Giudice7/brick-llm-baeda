import os
import json
import yaml

import rdflib
from rdflib import OWL, RDF, RDFS, SKOS


def load_exclusion_config(ontology_name: str):
    """Loads the URIs to exclude from the config.yaml file.

    Args:
        ontology_name (str): The name of the ontology folder.

    Returns:
        tuple: A tuple of URI prefixes to exclude.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, ontology_name, "config.yaml")
    if not os.path.exists(config_path):
        return tuple()

    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return tuple(config.get('uris_to_exclude', []))


def get_root_entities(ontology_name: str):
    """Identifies the root entities within the ontology's RDF graph.

    Args:
        ontology_name (str): The name of the ontology folder.

    Returns:
        list: A list of strings representing the URIs of the root entities.
    """
    ontology_path = os.path.join("ontologies", ontology_name, "ontology.ttl")
    graph = rdflib.Graph().parse(ontology_path, format="turtle")
    excluded_uris = load_exclusion_config(ontology_name)

    all_classes = set(graph.subjects(RDF.type, OWL.Class)).union(graph.subjects(RDF.type, RDFS.Class))

    valid_classes = {
        c for c in all_classes
        if isinstance(c, rdflib.URIRef) and not str(c).startswith(excluded_uris)
    }

    root_uris = []
    for c in valid_classes:
        has_valid_parent = False
        for parent in graph.objects(c, RDFS.subClassOf):
            if parent != c and parent != OWL.Thing and isinstance(parent, rdflib.URIRef):
                if parent in all_classes:
                    has_valid_parent = True
                    break
        if not has_valid_parent:
            root_uris.append(str(c))

    return root_uris
