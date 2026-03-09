import rdflib


def add_triple(graph: rdflib.Graph, subject_uri: str, predicate_uri: str, object_value: str, is_literal: bool) -> str:
    """Adds a new triple to the knowledge graph to fix ontological violations.

    Args:
        graph (rdflib.Graph): The current RDF graph being modified.
        subject_uri (str): The full URI of the subject node.
        predicate_uri (str): The full URI of the property/relationship.
        object_value (str): The URI of the target node, or the raw string value if it's a literal.
        is_literal (bool): True if the object_value is a literal (e.g., "100", "true"), False if it is a URI.

    Returns:
        str: A confirmation message indicating the triple was added.
    """
    s = rdflib.URIRef(subject_uri)
    p = rdflib.URIRef(predicate_uri)

    if is_literal:
        o = rdflib.Literal(object_value)
    else:
        o = rdflib.URIRef(object_value)

    graph.add((s, p, o))

    return f"Successfully added triple: [ {subject_uri}, {predicate_uri}, {object_value} ]"


def delete_triple(graph: rdflib.Graph, subject_uri: str, predicate_uri: str, object_value: str,
                  is_literal: bool) -> str:
    """Deletes an existing triple from the knowledge graph to resolve conflicts.

    Args:
        graph (rdflib.Graph): The current RDF graph being modified.
        subject_uri (str): The full URI of the subject node.
        predicate_uri (str): The full URI of the property/relationship.
        object_value (str): The URI of the target node, or the raw string value if it's a literal.
        is_literal (bool): True if the object_value is a literal, False if it is a URI.

    Returns:
        str: A confirmation message indicating the triple was removed, or a notice if it wasn't found.
    """
    s = rdflib.URIRef(subject_uri)
    p = rdflib.URIRef(predicate_uri)

    if is_literal:
        o = rdflib.Literal(object_value)
    else:
        o = rdflib.URIRef(object_value)

    if (s, p, o) in graph:
        graph.remove((s, p, o))
        return f"Successfully deleted triple: [ {subject_uri}, {predicate_uri}, {object_value} ]"
    else:
        return f"Triple not found in graph, nothing deleted: [ {subject_uri}, {predicate_uri}, {object_value} ]"


def retrieve_entity_info(graph: rdflib.Graph, entity_uri: str) -> str:
    entity = rdflib.URIRef(entity_uri)
    subgraph = rdflib.Graph()

    for prefix, namespace in graph.namespaces():
        subgraph.bind(prefix, namespace)

    for s, p, o in graph.triples((entity, None, None)):
        subgraph.add((s, p, o))

    for s, p, o in graph.triples((None, None, entity)):
        subgraph.add((s, p, o))

    if len(subgraph) == 0:
        return f"No triples found for entity: {entity_uri}"

    return subgraph.serialize(format="turtle")