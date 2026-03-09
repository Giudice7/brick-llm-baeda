import os
import json
import yaml
import rdflib
from rdflib.namespace import RDF, RDFS, OWL, SKOS, Namespace, XSD


def generate_hierarchy():
    """Builds a hierarchical dictionary of entities and saves it as hierarchy.json."""

    graph = rdflib.Graph().parse("ontology.ttl", format="turtle")

    uris_to_exclude = tuple()
    if os.path.exists("config.yaml"):
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
            uris_to_exclude = tuple(config.get('uris_to_exclude', []))

    deprecated_entities = set()
    for subject in graph.subjects(OWL.deprecated, None):
        for obj in graph.objects(subject, OWL.deprecated):
            if str(obj).lower() == "true":
                deprecated_entities.add(subject)

    all_classes = set(graph.subjects(RDF.type, OWL.Class)).union(graph.subjects(RDF.type, RDFS.Class))

    valid_classes = {
        c for c in all_classes
        if isinstance(c, rdflib.URIRef)
           and not str(c).startswith(uris_to_exclude)
           and c not in deprecated_entities
    }

    hierarchy_data = {}

    for c in valid_classes:
        uri_str = str(c)
        hierarchy_data[uri_str] = {
            "children": [],
            "description": ""
        }

        all_descriptions = []
        for d in graph.objects(c, SKOS.definition):
            all_descriptions.append(str(d))
        for comment in graph.objects(c, RDFS.comment):
            all_descriptions.append(str(comment))

        if all_descriptions:
            hierarchy_data[uri_str]["description"] = " ".join(all_descriptions)

    for c in valid_classes:
        parent_uri = str(c)
        for child in graph.subjects(RDFS.subClassOf, c):
            if child in valid_classes:
                hierarchy_data[parent_uri]["children"].append(str(child))

    with open("hierarchy.json", "w") as f:
        json.dump(hierarchy_data, f, indent=4)


def generate_relationships():
    g = rdflib.Graph().parse("ontology.ttl")
    BRICK = Namespace("https://brickschema.org/schema/Brick#")
    relationship_props = set()

    for s in g.subjects(RDF.type, OWL.ObjectProperty):
        if isinstance(s, rdflib.URIRef):
            relationship_props.add(s)

    for s in g.subjects(RDF.type, BRICK.Relationship):
        if isinstance(s, rdflib.URIRef):
            relationship_props.add(s)

    subproperties = {}
    for s, o in g.subject_objects(RDFS.subPropertyOf):
        if isinstance(s, rdflib.URIRef) and isinstance(o, rdflib.URIRef):
            subproperties.setdefault(o, set()).add(s)

    stack = [BRICK.Relationship]
    while stack:
        current = stack.pop()
        for child in subproperties.get(current, []):
            if child not in relationship_props:
                relationship_props.add(child)
                stack.append(child)

    relationships = {}

    for prop in relationship_props:
        prop_uri = str(prop)

        if not (prop_uri.startswith("https://brickschema.org") or prop_uri.startswith("https://w3id.org/rec#")):
            continue

        metadata_parts = []

        label = g.value(prop, RDFS.label)
        if label:
            metadata_parts.append(f"Label: {str(label)}")

        comment = g.value(prop, RDFS.comment)
        if comment:
            metadata_parts.append(f"Comment: {str(comment)}")

        definition = g.value(prop, SKOS.definition)
        if definition:
            metadata_parts.append(f"Definition: {str(definition)}")

        relationships[prop_uri] = " | ".join(metadata_parts)

    with open("relationships.json", "w", encoding="utf-8") as f:
        json.dump(relationships, f, indent=4)

# def generate_properties():
#
#     uris_to_exclude = tuple()
#     if os.path.exists("config.yaml"):
#         with open("config.yaml", 'r') as f:
#             config = yaml.safe_load(f) or {}
#             excluded = config.get('uris_to_exclude')
#             if excluded:
#                 uris_to_exclude = tuple(str(uri).strip() for uri in excluded)
#
#     g = rdflib.Graph()
#     g.parse("ontology.ttl", format="turtle")
#
#     deprecated_entities = set()
#     for subject in g.subjects(OWL.deprecated, None):
#         for obj in g.objects(subject, OWL.deprecated):
#             if str(obj).lower() == "true":
#                 deprecated_entities.add(str(subject))
#
#     rel_query = """
#     PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
#     PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
#     PREFIX brick: <https://brickschema.org/schema/Brick#>
#
#     SELECT DISTINCT ?path WHERE {
#         ?basePath rdf:type brick:Relationship .
#         ?path rdfs:subPropertyOf* ?basePath .
#     }
#     """
#     relationships = {str(row.path) for row in g.query(rel_query)}
#
#     all_properties = set(g.subjects(RDF.type, OWL.ObjectProperty)).union(
#         g.subjects(RDF.type, OWL.DatatypeProperty)
#     )
#
#     valid_properties = {
#         str(p) for p in all_properties
#         if isinstance(p, rdflib.URIRef)
#            and not str(p).startswith(uris_to_exclude)
#            and str(p) not in deprecated_entities
#            and str(p) not in relationships
#     }
#
#     domains_map = {}
#     domain_query = """
#     PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
#     PREFIX sh: <http://www.w3.org/ns/shacl#>
#
#     SELECT DISTINCT ?property ?domain WHERE {
#         {
#             ?property rdfs:domain ?domain .
#         }
#         UNION
#         {
#             ?domain sh:property ?shape .
#             ?shape sh:path ?property .
#         }
#         FILTER (isIRI(?domain))
#         FILTER (isIRI(?property))
#     }
#     """
#     for row in g.query(domain_query):
#         prop = str(row.property)
#         domain = str(row.domain)
#         if prop not in domains_map:
#             domains_map[prop] = set()
#         domains_map[prop].add(domain)
#
#     complex_shapes = {}
#     query_complex = """
#     PREFIX sh: <http://www.w3.org/ns/shacl#>
#     PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
#
#     SELECT DISTINCT ?property ?nestedProperty ?datatype ?inValue ?orDatatype WHERE {
#         ?shape sh:path ?property ;
#                sh:node ?nodeShape .
#         ?nodeShape sh:property ?nestedShape .
#         ?nestedShape sh:path ?nestedProperty .
#
#         OPTIONAL { ?nestedShape sh:datatype ?datatype . }
#         OPTIONAL { ?nestedShape sh:in/rdf:rest*/rdf:first ?inValue . }
#         OPTIONAL {
#             ?nestedShape sh:or/rdf:rest*/rdf:first ?orConstraint .
#             ?orConstraint sh:datatype|sh:class ?orDatatype .
#         }
#     }
#     """
#     for row in g.query(query_complex):
#         prop = str(row.property)
#         nested_prop = str(row.nestedProperty)
#
#         if prop not in complex_shapes:
#             complex_shapes[prop] = {}
#
#         if nested_prop not in complex_shapes[prop]:
#             complex_shapes[prop][nested_prop] = set()
#
#         if row.datatype:
#             complex_shapes[prop][nested_prop].add(str(row.datatype))
#         if row.orDatatype:
#             complex_shapes[prop][nested_prop].add(str(row.orDatatype))
#         if row.inValue:
#             complex_shapes[prop][nested_prop].add(str(row.inValue))
#
#     for prop in complex_shapes:
#         complex_shapes[prop] = {k: list(v) for k, v in complex_shapes[prop].items()}
#
#     direct_shapes = {}
#     query_direct = """
#     PREFIX sh: <http://www.w3.org/ns/shacl#>
#
#     SELECT DISTINCT ?property ?datatype ?targetClass ?nodeKind WHERE {
#         ?shape sh:path ?property .
#         FILTER NOT EXISTS { ?shape sh:node ?anyNode . }
#
#         OPTIONAL { ?shape sh:datatype ?datatype . }
#         OPTIONAL { ?shape sh:class ?targetClass . }
#         OPTIONAL { ?shape sh:nodeKind ?nodeKind . }
#     }
#     """
#     for row in g.query(query_direct):
#         prop = str(row.property)
#         if prop in complex_shapes:
#             continue
#
#         if prop not in direct_shapes:
#             direct_shapes[prop] = set()
#
#         if row.datatype:
#             direct_shapes[prop].add(str(row.datatype))
#         if row.targetClass:
#             direct_shapes[prop].add(str(row.targetClass))
#         if row.nodeKind:
#             direct_shapes[prop].add(str(row.nodeKind))
#
#     for prop in direct_shapes:
#         direct_shapes[prop] = list(direct_shapes[prop])
#
#     final_dict = {}
#
#     for prop in valid_properties:
#         domains = domains_map.get(prop, [])
#         shape = complex_shapes.get(prop, direct_shapes.get(prop, []))
#
#         for domain in domains:
#             if domain not in final_dict:
#                 final_dict[domain] = {}
#             final_dict[domain][prop] = shape
#
#     point_uri = "https://brickschema.org/schema/Brick#Point"
#     ext_ref_uri = "https://brickschema.org/schema/Brick/ref#hasExternalReference"
#     ts_ref_uri = "https://brickschema.org/schema/Brick/ref#TimeseriesReference"
#
#     if point_uri in final_dict:
#         if ext_ref_uri not in final_dict[point_uri]:
#             final_dict[point_uri][ext_ref_uri] = []
#         if isinstance(final_dict[point_uri][ext_ref_uri], list) and ts_ref_uri not in final_dict[point_uri][
#             ext_ref_uri]:
#             final_dict[point_uri][ext_ref_uri].append(ts_ref_uri)
#
#     meter_uri = "https://brickschema.org/schema/Brick#Meter"
#     virtual_meter_uri = "https://brickschema.org/schema/Brick#isVirtualMeter"
#     value_uri = "https://brickschema.org/schema/Brick#value"
#     boolean_uri = "http://www.w3.org/2001/XMLSchema#boolean"
#
#     if meter_uri in final_dict:
#         if virtual_meter_uri not in final_dict[meter_uri]:
#             final_dict[meter_uri][virtual_meter_uri] = {
#                 value_uri: [boolean_uri]
#             }
#
#     with open("properties.json", "w", encoding="utf-8") as f:
#         json.dump(final_dict, f, indent=4)

if __name__ == "__main__":
    generate_hierarchy()
    generate_relationships()