import rdflib
from typing import Dict, Any, Union, List

from langgraph.graph import StateGraph, START, END

from states import WorkflowState
from utils.validation import fix_malformed_literals
from validation import validation_node, route_after_validation
from agents import semantic_extractor, knowledge_graph_agent,  knowledge_graph_refactoring_agent


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

        self.workflow.add_node("semantic_extractor", semantic_extractor)
        self.workflow.add_node("knowledge_graph_agent", knowledge_graph_agent)
        self.workflow.add_node("validation_node", validation_node)
        self.workflow.add_node("knowledge_graph_refactoring", knowledge_graph_refactoring_agent)

        self.workflow.add_edge(START, "semantic_extractor")

        self.workflow.add_edge("semantic_extractor", "knowledge_graph_agent")

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
                    input_data, self.config, stream_mode="updates"
            ):
                for node_name, node_output in event.items():
                    print(f"\n{'=' * 50}")
                    print(f"🔄 UPDATE FROM NODE: {node_name}")
                    print(f"{'=' * 50}")

                    for key, value in node_output.items():
                        if key == "messages" and isinstance(value, list) and len(value) > 0:
                            print(
                                f"messages: [{len(value)} new messages] -> Last message type: {value[-1].__class__.__name__}")
                        else:
                            print(f"{key}: {value}\n")
                events.append(event)
            self.result = events[-1]
            return events
        else:
            self.result = self.workflow.invoke(input_data, self.config)
            return self.result

    def get_final_kg(self) -> rdflib.Graph:
        if self.result is None:
            raise ValueError("No result available. Please run the workflow first.")

        raw_graph = self.result["rdf_graphs"][-1]
        cleaned_graph = fix_malformed_literals(raw_graph)

        return cleaned_graph

    @staticmethod
    def calculate_token_usage(token_list: List[Dict[str, int]]) -> Dict[str, int]:
        aggregated_usage = {}
        if not token_list:
            return aggregated_usage

        for token_dict in token_list:
            for key, count in token_dict.items():
                if key not in aggregated_usage:
                    aggregated_usage[key] = 0
                aggregated_usage[key] += count

        return aggregated_usage

    def get_token_usage_summary(self) -> Dict[str, Dict[str, int]]:
        if self.result is None:
            raise ValueError("No result available. Please run the workflow first.")

        input_details = self.result["input_token_details"]
        output_details = self.result["output_token_details"]

        return {
            "input_tokens": self.calculate_token_usage(input_details),
            "output_tokens": self.calculate_token_usage(output_details)
        }
