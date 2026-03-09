from typing import Dict, Any, Union, List

from langgraph.graph import StateGraph, START, END

from states import WorkflowState
from validation import validation_node, route_after_validation
from agents import extract_entities_agent, extract_properties_agent, knowledge_graph_agent, \
    knowledge_graph_refactoring_agent


class BuildingKnowledgeGraphBuilder:
    def __init__(self, model, max_iterations: int = 3):
        self.model = model
        self.config = {
            "configurable": {
                "model": self.model,
                "max_iterations": max_iterations
            }
        }
        self.workflow = None
        self.result = None
        self.ttl_output = ""
        self.build_graph()

    def build_graph(self):
        self.workflow = StateGraph(WorkflowState)

        self.workflow.add_node("entity_extractor", extract_entities_agent)
        self.workflow.add_node("properties_extractor", extract_properties_agent)
        self.workflow.add_node("knowledge_graph_agent", knowledge_graph_agent)
        self.workflow.add_node("validation_node", validation_node)
        self.workflow.add_node("knowledge_graph_refactoring", knowledge_graph_refactoring_agent)

        self.workflow.add_edge(START, "entity_extractor")
        self.workflow.add_edge(START, "properties_extractor")

        self.workflow.add_edge(["entity_extractor", "properties_extractor"], "knowledge_graph_agent")

        self.workflow.add_edge("knowledge_graph_agent", "validation_node")

        self.workflow.add_conditional_edges(
            "validation_node",
            route_after_validation,
            {
                END: END,
                "knowledge_graph_refactoring": "knowledge_graph_refactoring"
            }
        )

        self.workflow.add_edge("knowledge_graph_refactoring", "validation_node")

        self.workflow = self.workflow.compile()

    def run(self, input_data: Dict[str, Any], stream: bool = False) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if "user_input" not in input_data:
            raise ValueError("Input data must contain a 'user_input' key.")

        if stream:
            events = []
            for event in self.workflow.stream(
                    input_data, self.config, stream_mode="values"
            ):
                events.append(event)
            self.result = events[-1]
            return events
        else:
            self.result = self.workflow.invoke(input_data, self.config)
            return self.result

    def get_final_kg(self):
        if self.result is None:
            raise ValueError("No result available. Please run the workflow first.")
        return self.result["rdf_graphs"][-1]

