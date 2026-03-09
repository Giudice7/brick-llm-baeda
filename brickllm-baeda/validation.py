from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from loguru import logger

from utils.validation import validate_graph, parse_shacl_results
from states import WorkflowState



def validation_node(state: WorkflowState) -> WorkflowState:
    graph = state.get("rdf_graphs", [])[-1]
    ontology_name = state.get("ontology_name")
    uri = state.get("uri")

    iteration = state.get("iteration", 0) + 1

    logger.info(f"🛡️ Validating graph against {ontology_name} SHACL shapes (Iteration {iteration})")

    conforms, results_graph, results_text, graph_inference = validate_graph(
        graph=graph,
        ontology_name=ontology_name,
        data_ns=uri
    )

    current_errors = {}
    if not conforms:
        current_errors = parse_shacl_results(results_graph)
        logger.debug(f"Errors in validation at iteration {iteration}: {current_errors}")

    logger.debug(f"Conformance at iteration {iteration}: {conforms}")

    inferred_graph_list = [graph_inference]
    validation_errors_list = [current_errors]

    return {
        "is_valid": conforms,
        "inferred_graph": inferred_graph_list,
        "iteration": iteration,
        "validation_errors": validation_errors_list
    }


def route_after_validation(state: WorkflowState, config: RunnableConfig) -> str:
    is_valid = state.get("is_valid")
    iteration = state.get("iteration", 0)
    max_iterations = config.get("configurable", {}).get("max_iterations", 3)

    if is_valid or iteration >= max_iterations:
        return END

    return "knowledge_graph_refactoring"