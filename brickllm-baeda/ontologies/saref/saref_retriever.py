import rdflib
from rdflib.namespace import RDF, RDFS, OWL
from typing import List, Dict, Any, Set

from ontologies.onto_retriever import OntoRetriever

SKOS = rdflib.Namespace("http://www.w3.org/2004/02/skos/core#")


class SarefRetriever(OntoRetriever):

    def get_superclasses(self, entity_uri: rdflib.URIRef) -> Set[str]:
        supers = set()
        if not isinstance(entity_uri, rdflib.URIRef):
            return supers

        stack = [entity_uri]

        for t in self.g.objects(entity_uri, RDF.type):
            if isinstance(t, rdflib.URIRef) and str(t) not in [
                "http://www.w3.org/2002/07/owl#NamedIndividual",
                "http://www.w3.org/2002/07/owl#Class",
                "http://www.w3.org/2002/07/owl#ObjectProperty",
                "http://www.w3.org/2002/07/owl#DatatypeProperty"
            ]:
                stack.append(t)

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

    def resolve_owl_class(self, node: rdflib.term.Node, visited: Set[rdflib.term.Node] = None) -> List[str]:
        if visited is None:
            visited = set()
        if node in visited:
            return []
        visited.add(node)

        targets = []
        if isinstance(node, rdflib.URIRef):
            targets.append(str(node))
            return targets

        for union_list in self.g.objects(node, OWL.unionOf):
            curr = union_list
            while curr and curr != RDF.nil:
                first = self.g.value(curr, RDF.first)
                if first:
                    targets.extend(self.resolve_owl_class(first, visited.copy()))
                curr = self.g.value(curr, RDF.rest)

        for intersection_list in self.g.objects(node, OWL.intersectionOf):
            curr = intersection_list
            while curr and curr != RDF.nil:
                first = self.g.value(curr, RDF.first)
                if first:
                    targets.extend(self.resolve_owl_class(first, visited.copy()))
                curr = self.g.value(curr, RDF.rest)

        return list(set(targets))

    def get_hierarchy(self) -> Dict[str, Dict[str, Any]]:
        hierarchy = {}

        for owl_class in self.g.subjects(RDF.type, OWL.Class):
            if not isinstance(owl_class, rdflib.URIRef):
                continue

            class_str = str(owl_class)

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

                    child_dep = self.g.value(child, OWL.deprecated)
                    if child_dep and str(child_dep).lower() == "true":
                        continue
                    hierarchy[class_str]["children"].append(child_str)

        return hierarchy

    def get_object_properties(self) -> Dict[str, Dict[str, Any]]:
        properties = {}

        for obj_prop in self.g.subjects(RDF.type, OWL.ObjectProperty):
            if not isinstance(obj_prop, rdflib.URIRef):
                continue

            prop_str = str(obj_prop)

            desc_parts = []
            definition = self.g.value(obj_prop, SKOS.definition)
            comment = self.g.value(obj_prop, RDFS.comment)

            if definition:
                desc_parts.append(str(definition))
            if comment:
                desc_parts.append(str(comment))

            properties[prop_str] = {
                "description": " ".join(set(desc_parts))
            }

        return properties

    def get_data_properties(self) -> Dict[str, Dict[str, Any]]:
        properties = {}

        for data_prop in self.g.subjects(RDF.type, OWL.DatatypeProperty):
            if not isinstance(data_prop, rdflib.URIRef):
                continue

            prop_str = str(data_prop)

            desc_parts = []
            definition = self.g.value(data_prop, SKOS.definition)
            comment = self.g.value(data_prop, RDFS.comment)

            if definition:
                desc_parts.append(str(definition))
            if comment:
                desc_parts.append(str(comment))

            properties[prop_str] = {
                "description": " ".join(set(desc_parts))
            }

        return properties

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

                for restriction in self.g.objects(cls_uri, RDFS.subClassOf):
                    if not isinstance(restriction, rdflib.BNode):
                        continue

                    is_restriction = False
                    for type_val in self.g.objects(restriction, RDF.type):
                        if type_val == OWL.Restriction:
                            is_restriction = True
                            break

                    if not is_restriction:
                        continue

                    for prop in self.g.objects(restriction, OWL.onProperty):
                        path_str = str(prop)
                        if path_str not in all_requested_properties:
                            continue

                        if path_str not in subject_dict:
                            subject_dict[path_str] = []

                        allowed_targets = set()

                        for target in self.g.objects(restriction, OWL.someValuesFrom):
                            allowed_targets.update(self.resolve_owl_class(target))
                        for target in self.g.objects(restriction, OWL.allValuesFrom):
                            allowed_targets.update(self.resolve_owl_class(target))
                        for target in self.g.objects(restriction, OWL.onClass):
                            allowed_targets.update(self.resolve_owl_class(target))
                        for target in self.g.objects(restriction, OWL.hasValue):
                            allowed_targets.add(str(target))

                        for target_class_str in allowed_targets:
                            matched = False
                            for target_ent in entities:
                                if target_class_str in entity_superclasses[target_ent]:
                                    if target_ent not in subject_dict[path_str]:
                                        subject_dict[path_str].append(target_ent)
                                    matched = True
                            if not matched and target_class_str not in subject_dict[path_str]:
                                subject_dict[path_str].append(target_class_str)

            for prop_str in all_requested_properties:
                prop_uri = rdflib.URIRef(prop_str)

                domains = set()
                ranges = set()

                for d in self.g.objects(prop_uri, RDFS.domain):
                    domains.update(self.resolve_owl_class(d))
                for r in self.g.objects(prop_uri, RDFS.range):
                    ranges.update(self.resolve_owl_class(r))

                inverse_props = list(self.g.objects(prop_uri, OWL.inverseOf))
                inverse_props.extend(list(self.g.subjects(OWL.inverseOf, prop_uri)))

                for inv_p in inverse_props:
                    for d in self.g.objects(inv_p, RDFS.domain):
                        ranges.update(self.resolve_owl_class(d))
                    for r in self.g.objects(inv_p, RDFS.range):
                        domains.update(self.resolve_owl_class(r))

                if domains and any(d in subject_supers for d in domains):
                    if prop_str not in subject_dict or not subject_dict[prop_str]:
                        if prop_str not in subject_dict:
                            subject_dict[prop_str] = []
                        for r in ranges:
                            matched = False
                            for target_ent in entities:
                                if r in entity_superclasses[target_ent]:
                                    if target_ent not in subject_dict[prop_str]:
                                        subject_dict[prop_str].append(target_ent)
                                    matched = True
                            if not matched and r not in subject_dict[prop_str]:
                                subject_dict[prop_str].append(r)

            if subject_dict:
                result[subject_ent] = subject_dict
            else:
                result[subject_ent] = {}

        return result


if __name__ == "__main__":
    import json

    retriever = SarefRetriever()

    sample_entities = [
        "https://saref.etsi.org/saref4bldg/Building",
        "https://saref.etsi.org/saref4bldg/BuildingSpace",
        "https://saref.etsi.org/saref4bldg/PhysicalObject",
        "https://saref.etsi.org/core/Device",
        "https://saref.etsi.org/core/Sensor",
        "https://saref.etsi.org/core/TemperatureSensor",
        "https://saref.etsi.org/core/Actuator",
        "https://saref.etsi.org/core/Meter",
        "https://saref.etsi.org/core/Property",
        "https://saref.etsi.org/core/Observation"
    ]

    sample_relationships = [
        "https://saref.etsi.org/saref4bldg/hasSpace",
        "https://saref.etsi.org/saref4bldg/contains",
        "https://saref.etsi.org/core/observes",
        "https://saref.etsi.org/core/controls",
        "https://saref.etsi.org/core/measuresProperty",
        "https://saref.etsi.org/core/hasProperty",
        "https://saref.etsi.org/core/isPropertyOf"
    ]

    sample_properties = [
        "https://saref.etsi.org/core/hasValue",
        "https://saref.etsi.org/core/hasTimestamp"
    ]

    supported_mapping = retriever.get_supported_relationships(
        sample_entities,
        sample_relationships,
        sample_properties
    )

    print(json.dumps(supported_mapping, indent=4))