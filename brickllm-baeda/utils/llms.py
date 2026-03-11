from typing import Any, Tuple, List

from schemas import InputTokenDetails, OutputTokenDetails
from langchain_core.messages import AIMessage, InputTokenDetails


def calculate_token_usage(messages: List[Any]) -> Tuple[InputTokenDetails, OutputTokenDetails]:
    """
    Calculate token usage per message.
    Args:
        messages: List of messages to analyze for token usage.

    Returns: A tuple containing two dictionaries: input_summary and output_summary, each with token usage details.

    """
    input_summary: InputTokenDetails = {
        "total_tokens": 0,
        "audio": 0,
        "cache_creation": 0,
        "cache_read": 0,
        "cache_read_over_200k": 0,
        "ephemeral_5m_input_tokens": 0,
        "ephemeral_1h_input_tokens": 0
    }

    output_summary: OutputTokenDetails = {
        "total_tokens": 0,
        "audio": 0,
        "reasoning": 0
    }

    for message in messages:
        if isinstance(message, AIMessage) and hasattr(message, "usage_metadata") and message.usage_metadata:
            metadata = message.usage_metadata

            input_summary["total_tokens"] += metadata.get("input_tokens", 0)
            in_details = metadata.get("input_token_details", {})
            if in_details:
                input_summary["audio"] += in_details.get("audio", 0)
                input_summary["cache_creation"] += in_details.get("cache_creation", 0)
                input_summary["cache_read"] += in_details.get("cache_read", 0)
                input_summary["cache_read_over_200k"] += in_details.get("cache_read_over_200k", 0)
                input_summary["ephemeral_5m_input_tokens"] += in_details.get("ephemeral_5m_input_tokens", 0)
                input_summary["ephemeral_1h_input_tokens"] += in_details.get("ephemeral_1h_input_tokens", 0)

            output_summary["total_tokens"] += metadata.get("output_tokens", 0)
            out_details = metadata.get("output_token_details", {})
            if out_details:
                output_summary["audio"] += out_details.get("audio", 0)
                output_summary["reasoning"] += out_details.get("reasoning", 0)

    return input_summary, output_summary