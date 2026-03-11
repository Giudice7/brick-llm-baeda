import os
import yaml
import rdflib
from rdflib.namespace import RDF, RDFS, OWL, Namespace
from typing import List, Dict, Any, Set
from ...ontologies.onto_retriever import OntoRetriever

SH = Namespace("http://www.w3.org/ns/shacl#")
SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

base_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(base_dir, "config.yaml"), "r") as f:
    config = yaml.safe_load(f)

IGNORED_URIS = config["uris_to_exclude"]

class BrickRetriever(OntoRetriever):

    def get_superclasses(self, entity_uri: rdflib.URIRef) -> Set[str]:
        supers = set()
        if not isinstance(entity_uri, rdflib.URIRef):
            return supers

        stack = [entity_uri]
        while stack:
            current = stack.pop()
            if isinstance(current, rdflib.URIRef):
                current_str = str(current)
                if current_str in ["http://www.w3.org/2000/01/rdf-schema#Resource",
                                   "http://www.w3.org/2002/07/owl#Thing"]:
                    continue
                if current_str not in supers:
                    supers.add(current_str)
                    for parent in self.g.objects(current, RDFS.subClassOf):
                        stack.append(parent)
        return supers

    def get_superproperties(self, prop_uri: rdflib.URIRef) -> Set[rdflib.URIRef]:
        supers = set()
        stack = [prop_uri]
        while stack:
            current = stack.pop()
            if current not in supers:
                supers.add(current)
                for parent in self.g.objects(current, RDFS.subPropertyOf):
                    if isinstance(parent, rdflib.URIRef):
                        stack.append(parent)
        return supers

    def get_hierarchy(self) -> Dict[str, Dict[str, Any]]:
        hierarchy = {}

        for owl_class in set(self.g.subjects(RDF.type, OWL.Class)).union(self.g.subjects(RDF.type, RDFS.Class)):
            if not isinstance(owl_class, rdflib.URIRef):
                continue

            class_str = str(owl_class)
            if any(ignored in class_str for ignored in IGNORED_URIS):
                continue

            deprecated_val = self.g.value(owl_class, OWL.deprecated)
            if deprecated_val and str(deprecated_val).lower() == "true":
                continue

            desc_parts = []
            definition = self.g.value(owl_class, SKOS.definition)
            comment = self.g.value(owl_class, RDFS.comment)

            if definition:
                desc_parts.append(str(definition))
            if comment:
                desc_parts.append(str(comment))

            hierarchy[class_str] = {
                "children": [],
                "description": " ".join(desc_parts)
            }

            for child in self.g.subjects(RDFS.subClassOf, owl_class):
                if isinstance(child, rdflib.URIRef):
                    child_str = str(child)
                    if any(ignored in child_str for ignored in IGNORED_URIS):
                        continue

                    child_dep = self.g.value(child, OWL.deprecated)
                    if child_dep and str(child_dep).lower() == "true":
                        continue
                    hierarchy[class_str]["children"].append(child_str)

        return hierarchy

    def get_data_properties(self) -> Dict[str, Dict[str, Any]]:
        properties = {}

        for data_prop in self.g.subjects(RDF.type, OWL.DatatypeProperty):
            if not isinstance(data_prop, rdflib.URIRef):
                continue

            prop_str = str(data_prop)
            if any(ignored in prop_str for ignored in IGNORED_URIS):
                continue

            deprecated = self.g.value(data_prop, OWL.deprecated)
            if deprecated and str(deprecated).lower() == "true":
                continue

            desc_parts = []
            definition = self.g.value(data_prop, SKOS.definition)
            comment = self.g.value(data_prop, RDFS.comment)

            if definition:
                desc_parts.append(str(definition))
            if comment:
                desc_parts.append(str(comment))

            for prop_shape in self.g.subjects(SH.path, data_prop):
                local_definition = self.g.value(prop_shape, SKOS.definition)
                local_comment = self.g.value(prop_shape, RDFS.comment)
                if local_definition:
                    desc_parts.append(str(local_definition))
                if local_comment:
                    desc_parts.append(str(local_comment))

            properties[prop_str] = {
                "description": " ".join(set(desc_parts))
            }

        return properties

    def get_object_properties(self) -> Dict[str, Dict[str, Any]]:
        properties = {}

        for obj_prop in self.g.subjects(RDF.type, OWL.ObjectProperty):
            if not isinstance(obj_prop, rdflib.URIRef):
                continue

            prop_str = str(obj_prop)
            if any(ignored in prop_str for ignored in IGNORED_URIS):
                continue

            deprecated = self.g.value(obj_prop, OWL.deprecated)
            if deprecated and str(deprecated).lower() == "true":
                continue

            desc_parts = []
            definition = self.g.value(obj_prop, SKOS.definition)
            comment = self.g.value(obj_prop, RDFS.comment)

            if definition:
                desc_parts.append(str(definition))
            if comment:
                desc_parts.append(str(comment))

            for prop_shape in self.g.subjects(SH.path, obj_prop):
                local_definition = self.g.value(prop_shape, SKOS.definition)
                local_comment = self.g.value(prop_shape, RDFS.comment)
                if local_definition:
                    desc_parts.append(str(local_definition))
                if local_comment:
                    desc_parts.append(str(local_comment))

            properties[prop_str] = {
                "description": " ".join(set(desc_parts))
            }

        return properties

    def resolve_complex_shape(self, node_shape: rdflib.term.Node, visited: Set[rdflib.term.Node] = None) -> Dict[
        str, List[Any]]:
        if visited is None:
            visited = set()
        if node_shape in visited:
            return {}
        visited.add(node_shape)

        complex_dict = {}
        for prop in self.g.objects(node_shape, SH.property):
            path = self.g.value(prop, SH.path)
            if path:
                path_str = str(path)
                targs = []

                for target_dt in self.g.objects(prop, SH.datatype):
                    targs.append(str(target_dt))
                for target_class in self.g.objects(prop, SH["class"]):
                    targs.append(str(target_class))
                for in_list in self.g.objects(prop, SH["in"]):
                    curr = in_list
                    while curr and curr != RDF.nil:
                        first = self.g.value(curr, RDF.first)
                        if first is not None:
                            targs.append(str(first))
                        curr = self.g.value(curr, RDF.rest)
                for target_node in self.g.objects(prop, SH.node):
                    if list(self.g.objects(target_node, SH.property)):
                        cdict = self.resolve_complex_shape(target_node, visited.copy())
                        if cdict:
                            targs.append(cdict)
                    else:
                        targs.append(str(target_node))
                for or_list in self.g.objects(prop, SH["or"]):
                    curr = or_list
                    while curr and curr != RDF.nil:
                        first = self.g.value(curr, RDF.first)
                        if first:
                            for target_dt in self.g.objects(first, SH.datatype):
                                targs.append(str(target_dt))
                            for target_class in self.g.objects(first, SH["class"]):
                                targs.append(str(target_class))
                            for target_node in self.g.objects(first, SH.node):
                                if list(self.g.objects(target_node, SH.property)):
                                    cdict = self.resolve_complex_shape(target_node, visited.copy())
                                    if cdict:
                                        targs.append(cdict)
                                else:
                                    targs.append(str(target_node))
                        curr = self.g.value(curr, RDF.rest)

                unique_targs = []
                for t in targs:
                    if t not in unique_targs:
                        unique_targs.append(t)

                complex_dict[path_str] = unique_targs

        return complex_dict

    def get_supported_relationships(self, entities: List[str], relationships: List[str], properties: List[str]) -> Dict[
        str, Dict[str, List[Any]]]:
        """
        Obtains the supported relationships and properties for the given entities.
        Args:
            entities (list): A list of entity URIs (strings) for which to retrieve supported relationships and properties.
            relationships: A list of object property URIs (strings) that were extracted by the agent and should be validated against the ontology.
            properties: A list of datatype property URIs (strings) that were extracted by the agent and should be validated against the ontology.

        Returns:
            dict: A dictionary where each key is a subject entity URI (string) from the input entities list, and the value is another dictionary. This inner dictionary maps valid relationship/property URIs (strings) to a list of valid target URIs (strings) from the input entities list or literal values, based on the constraints defined in the ontology.
        """

        result = {}
        all_requested_properties = set(relationships + properties)

        entity_superclasses = {}
        for ent in entities:
            entity_superclasses[ent] = self.get_superclasses(rdflib.URIRef(ent))

        for subject_ent in entities:
            subject_supers = entity_superclasses[subject_ent]
            subject_dict = {}

            for cls_str in subject_supers:
                cls_uri = rdflib.URIRef(cls_str)

                for prop_shape in self.g.objects(cls_uri, SH.property):
                    path = self.g.value(prop_shape, SH.path)
                    if not path:
                        continue

                    path_str = str(path)
                    if path_str not in all_requested_properties:
                        continue

                    if path_str not in subject_dict:
                        subject_dict[path_str] = []

                    allowed_target_classes = set()
                    allowed_literals = set()
                    complex_shapes = []

                    for target_class in self.g.objects(prop_shape, SH["class"]):
                        if isinstance(target_class, rdflib.URIRef):
                            allowed_target_classes.add(str(target_class))
                    for target_dt in self.g.objects(prop_shape, SH.datatype):
                        if isinstance(target_dt, rdflib.URIRef):
                            allowed_literals.add(str(target_dt))
                    for in_list in self.g.objects(prop_shape, SH["in"]):
                        curr = in_list
                        while curr and curr != RDF.nil:
                            first = self.g.value(curr, RDF.first)
                            if first is not None:
                                allowed_literals.add(str(first))
                            curr = self.g.value(curr, RDF.rest)

                    for target_node in self.g.objects(prop_shape, SH.node):
                        if isinstance(target_node, rdflib.URIRef) and not list(
                                self.g.objects(target_node, SH.property)):
                            allowed_target_classes.add(str(target_node))
                        else:
                            cdict = self.resolve_complex_shape(target_node)
                            if cdict and cdict not in complex_shapes:
                                complex_shapes.append(cdict)

                    for or_list in self.g.objects(prop_shape, SH["or"]):
                        curr = or_list
                        while curr and curr != RDF.nil:
                            first = self.g.value(curr, RDF.first)
                            if first:
                                for target_class in self.g.objects(first, SH["class"]):
                                    if isinstance(target_class, rdflib.URIRef):
                                        allowed_target_classes.add(str(target_class))
                                for target_dt in self.g.objects(first, SH.datatype):
                                    if isinstance(target_dt, rdflib.URIRef):
                                        allowed_literals.add(str(target_dt))
                                for target_node in self.g.objects(first, SH.node):
                                    if isinstance(target_node, rdflib.URIRef) and not list(
                                            self.g.objects(target_node, SH.property)):
                                        allowed_target_classes.add(str(target_node))
                                    else:
                                        cdict = self.resolve_complex_shape(target_node)
                                        if cdict and cdict not in complex_shapes:
                                            complex_shapes.append(cdict)
                            curr = self.g.value(curr, RDF.rest)

                    # Match explicitly provided entities against allowed classes
                    for tc in allowed_target_classes:
                        for target_ent in entities:
                            if tc in entity_superclasses[target_ent]:
                                if target_ent not in subject_dict[path_str]:
                                    subject_dict[path_str].append(target_ent)

                    # Add literal values (datatypes, enumerations)
                    for lit in allowed_literals:
                        if lit not in subject_dict[path_str]:
                            subject_dict[path_str].append(lit)

                    # Add resolved complex shapes
                    for cs in complex_shapes:
                        if cs not in subject_dict[path_str]:
                            subject_dict[path_str].append(cs)

            # Global domain/range fallback for generic properties (like in REC)
            for prop_str in all_requested_properties:
                prop_uri = rdflib.URIRef(prop_str)
                domains = [str(d) for d in self.g.objects(prop_uri, RDFS.domain) if isinstance(d, rdflib.URIRef)]
                ranges = [str(r) for r in self.g.objects(prop_uri, RDFS.range) if isinstance(r, rdflib.URIRef)]

                if domains and any(d in subject_supers for d in domains):
                    if prop_str not in subject_dict:
                        subject_dict[prop_str] = []
                    for r in ranges:
                        for target_ent in entities:
                            if r in entity_superclasses[target_ent]:
                                if target_ent not in subject_dict[prop_str]:
                                    subject_dict[prop_str].append(target_ent)

            if subject_dict:
                result[subject_ent] = subject_dict
            else:
                result[subject_ent] = {}

        return result
