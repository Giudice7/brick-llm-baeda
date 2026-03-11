import os
import json
import rdflib
import owlrl
from pyshacl import validate
from rdflib.collection import Collection
from rdflib.namespace import RDF, OWL, RDFS


def trace_class_hierarchy(cls: rdflib.term.Node, source_graph: rdflib.Graph, target_graph: rdflib.Graph):
    """Recursively traces and extracts a class hierarchy from an ontology.

    Scans the source graph for triples associated with a specific class and adds
    them to the target graph. It recursively traverses up the ontology tree
    whenever it encounters rdfs:subClassOf or owl:equivalentClass relationships.

    Args:
        cls (rdflib.term.Node): The RDF node representing the class to trace.
        source_graph (rdflib.Graph): The full ontology graph being queried.
        target_graph (rdflib.Graph): The subset graph to populate with the extracted triples.
    """
    for _, p, o in source_graph.triples((cls, None, None)):
        if (cls, p, o) not in target_graph:
            target_graph.add((cls, p, o))
            if p in (RDFS.subClassOf, OWL.equivalentClass) and isinstance(o, rdflib.URIRef):
                trace_class_hierarchy(o, source_graph, target_graph)


def trace_property_hierarchy(prop: rdflib.term.Node, source_graph: rdflib.Graph, target_graph: rdflib.Graph):
    """Recursively traces and extracts a property hierarchy from an ontology.

    Scans the source graph for triples associated with a specific property and adds
    them to the target graph. It recursively traverses up the ontology tree
    whenever it encounters rdfs:subPropertyOf or owl:equivalentProperty relationships.

    Args:
        prop (rdflib.term.Node): The RDF node representing the property to trace.
        source_graph (rdflib.Graph): The full ontology graph being queried.
        target_graph (rdflib.Graph): The subset graph to populate with the extracted triples.
    """
    for _, p, o in source_graph.triples((prop, None, None)):
        if (prop, p, o) not in target_graph:
            target_graph.add((prop, p, o))
            if p in (RDFS.subPropertyOf, OWL.equivalentProperty) and isinstance(o, rdflib.URIRef):
                trace_property_hierarchy(o, source_graph, target_graph)


def get_relevant_owl_ontology(data_graph: rdflib.Graph, full_ontology: rdflib.Graph) -> rdflib.Graph:
    """Creates a lightweight sub-ontology based on the instances in a data graph.

    Analyzes the provided data graph to identify all actively used RDF types (classes)
    and predicates (properties). It then builds and returns a new graph containing
    only the ontological hierarchies relevant to those specific classes and properties.

    Args:
        data_graph (rdflib.Graph): The graph containing instance data.
        full_ontology (rdflib.Graph): The complete ontology graph to extract from.

    Returns:
        rdflib.Graph: A new graph containing the filtered, relevant sub-ontology.
    """
    relevant = rdflib.Graph()
    used_classes = set(data_graph.objects(None, RDF.type))
    used_properties = set(data_graph.predicates())

    for cls in used_classes:
        if isinstance(cls, rdflib.URIRef):
            trace_class_hierarchy(cls, full_ontology, relevant)

    for prop in used_properties:
        if isinstance(prop, rdflib.URIRef):
            trace_property_hierarchy(prop, full_ontology, relevant)

    return relevant


def extract_instance_data(combined_graph: rdflib.Graph, data_namespace: str) -> rdflib.Graph:
    """Filters an expanded graph to isolate A-Box instance data.

    Iterates through a reasoned graph and extracts only the triples that describe
    instances belonging to the specified target namespace. It deliberately excludes
    reflexive owl:sameAs triples and literal subjects. Binds namespaces dynamically
    from the namespaces.json artifact.

    Args:
        combined_graph (rdflib.Graph): The fully reasoned graph containing both schema and instances.
        data_namespace (str): The URI string of the namespace representing the instance data.

    Returns:
        rdflib.Graph: A clean graph containing only the inferred instance triples, with standard namespaces bound.
    """
    cleaned = rdflib.Graph()

    for s, p, o in combined_graph:
        if p == OWL.sameAs and s == o:
            continue
        if isinstance(s, rdflib.Literal):
            continue
        if isinstance(s, rdflib.URIRef) and str(s).startswith(data_namespace):
            cleaned.add((s, p, o))

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    namespaces_path = os.path.join(base_dir, "ontologies", "namespaces.json")

    if os.path.exists(namespaces_path):
        with open(namespaces_path, "r", encoding="utf-8") as f:
            ns_dict = json.load(f)
            for prefix, uri in ns_dict.items():
                cleaned.bind(prefix, rdflib.Namespace(uri))

    cleaned.bind("bldg", rdflib.Namespace(data_namespace))
    return cleaned


def inference(data_graph: rdflib.Graph, full_ontology: rdflib.Graph, data_ns: str) -> rdflib.Graph:
    """Executes optimized OWL 2 RL inference on a dataset.

    Combines the instance data with a dynamically filtered sub-ontology to minimize
    computational overhead. Applies deductive closure expansion, and then isolates
    the resulting instance data from the schema rules.

    Args:
        data_graph (rdflib.Graph): The graph containing the base instance data.
        full_ontology (rdflib.Graph): The complete schema/ontology graph.
        data_ns (str): The namespace URI strictly associated with the instance data.

    Returns:
        rdflib.Graph: The fully inferred graph containing only instance data.
    """
    relevant_ontology = get_relevant_owl_ontology(data_graph, full_ontology)
    combined = data_graph + relevant_ontology

    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics).expand(combined)
    return extract_instance_data(combined, data_ns)


def fix_shacl_violations(ontology_graph: rdflib.Graph):
    """Repairs standard SHACL syntax violations directly within an ontology graph.

    Identifies shape nodes within the ontology that incorrectly possess multiple
    sh:not predicates. Removes the illegal redundant predicates and repackages
    them into a mathematically equivalent, W3C-compliant sh:or list nested within
    a single sh:not predicate. Modifies the graph in place.

    Args:
        ontology_graph (rdflib.Graph): The ontology graph to be repaired.
    """
    sh = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    for s in set(ontology_graph.subjects(sh['not'], None)):
        nots = list(ontology_graph.objects(s, sh['not']))
        if len(nots) > 1:
            for obj in nots:
                ontology_graph.remove((s, sh['not'], obj))

            or_node = rdflib.BNode()
            list_node = rdflib.BNode()
            Collection(ontology_graph, list_node, nots)

            ontology_graph.add((or_node, sh['or'], list_node))
            ontology_graph.add((s, sh['not'], or_node))


def validate_graph(graph: rdflib.Graph, ontology_name: str, data_ns: str) -> tuple:
    """Validates an RDF graph against a specified ontology using SHACL.

    Loads the base ontology and any local enrichments, applies OWL 2 RL inference
    to the target graph, and evaluates the reasoned graph against the SHACL shapes
    defined in the ontology.

    Args:
        graph (rdflib.Graph): The RDF graph containing the instance data to validate.
        ontology_name (str): The name of the ontology directory (e.g., "Brick") to load shapes from.
        data_ns (str): The namespace URI associated with the instance data.

    Returns:
        tuple: A 4-element tuple containing:
            - conforms (bool): True if the graph passes validation, False otherwise.
            - results_graph (rdflib.Graph): The SHACL validation report as an RDF graph.
            - results_text (str): A human-readable text representation of the validation report.
            - graph_inference (rdflib.Graph): The expanded graph after OWL inference.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ontology_path = os.path.join(base_dir, "ontologies", ontology_name, "ontology.ttl")

    ontology_graph = rdflib.Graph()
    ontology_graph.parse(ontology_path, format="turtle")

    if ontology_name.lower() == "brick":
        fix_shacl_violations(ontology_graph)

    graph_inference = inference(graph, ontology_graph, data_ns)

    conforms, results_graph, results_text = validate(
        graph_inference,
        ont_graph=ontology_graph,
        shacl_graph=ontology_graph,
        allow_infos=True,
        allow_warnings=True,
        abort_on_first=False,
        advanced=True,
        iterate_rules=True,
        inplace=False
    )

    return conforms, results_graph, results_text, graph_inference


def parse_shacl_results(results_graph: rdflib.Graph) -> dict:
    """Parses a SHACL validation graph and groups errors by focus node.

    Queries the validation report for all sh:ValidationResult instances. Extracts
    the involved focus node, the property path, the human-readable message, the
    violating value, and the specific constraint component that failed.

    Args:
        results_graph (rdflib.Graph): The RDF graph containing the SHACL validation report.

    Returns:
        dict: A dictionary mapping focus node URIs (str) to a list of error dictionaries.
              Each error dictionary contains 'message', 'constraint_component', and optionally
              'path' and 'value'.
    """
    sh = rdflib.Namespace("http://www.w3.org/ns/shacl#")
    errors_by_node = {}

    for result in results_graph.subjects(RDF.type, sh.ValidationResult):
        focus_node = results_graph.value(result, sh.focusNode)
        if not focus_node:
            continue

        fn_str = str(focus_node)
        if fn_str not in errors_by_node:
            errors_by_node[fn_str] = []

        result_path = results_graph.value(result, sh.resultPath)
        result_message = results_graph.value(result, sh.resultMessage)
        value = results_graph.value(result, sh.value)
        constraint_cmp = results_graph.value(result, sh.sourceConstraintComponent)

        error_detail = {
            "message": str(result_message) if result_message else "No message provided in SHACL report",
            "constraint_component": str(constraint_cmp).split("#")[-1] if constraint_cmp else "Unknown"
        }

        if result_path:
            error_detail["path"] = str(result_path)
        if value:
            error_detail["value"] = str(value)

        errors_by_node[fn_str].append(error_detail)

    return errors_by_node

