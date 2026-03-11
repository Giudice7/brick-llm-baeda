from ontologies.utils import get_root_entities
from ontologies.Brick.brick_retriever import BrickRetriever
from ontologies.saref.saref_retriever import SarefRetriever

onto_retriever_mapping = {
    "Brick": BrickRetriever(),
    "saref": SarefRetriever()
}
