import json
import uuid
from typing import AsyncGenerator, Any
from ai.agent import get_agent
from ai.tools import set_user_context, TOOL_NAMES
from api.v1.utils.dependencies import get_db


def format_sse_event(data: dict) -> str:
    """
    Format a dictionary as a Server-Sent Events (SSE) message.

    Converts the provided data dictionary to JSON and wraps it in the SSE format
    with the "data: " prefix and double newline terminator.

    Args:
        data: Dictionary to be formatted as SSE event data.

    Returns:
        Formatted SSE string in the format: "data: {json_data}\\n\\n"

    Example:
        >>> format_sse_event({"type": "text", "content": "Hello"})
        'data: {"type": "text", "content": "Hello"}\\n\\n'
    """
    json_data = json.dumps(data, ensure_ascii=False)
    return f"data: {json_data}\n\n"


def extract_text_from_message(message: Any) -> str:
    """
    Extract text content from a message object, handling various formats.

    This function handles multiple message content formats:
    - String content: Returns the string if non-empty
    - List content: Extracts text from items with type "text" or items containing "text" key
    - Other formats: Converts to string if non-empty

    The function filters out tool calls and function messages, returning None for those.

    Args:
        message: Message object that may have a 'content' attribute. Can be a LangChain
                 message object, dict, or other object with content.

    Returns:
        Extracted text string if found and non-empty, None otherwise. Returns None for:
        - Messages with tool_calls
        - Tool or Function message types
        - Empty or whitespace-only content

    Example:
        >>> # String content
        >>> msg = type('Message', (), {'content': 'Hello world'})()
        >>> extract_text_from_message(msg)
        'Hello world'

        >>> # List content with type "text"
        >>> msg = type('Message', (), {'content': [{'type': 'text', 'text': 'Hello'}]})()
        >>> extract_text_from_message(msg)
        'Hello'
    """
    if hasattr(message, "tool_calls") and message.tool_calls:
        return None

    message_type = getattr(message, "__class__", None)
    if message_type:
        type_name = message_type.__name__
        if "Tool" in type_name or "Function" in type_name:
            return None

    if hasattr(message, "content"):
        content = message.content
        if isinstance(content, str):
            return content if content.strip() else None
        elif isinstance(content, list):
            texts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text = item.get("text", "")
                        if text.strip():
                            texts.append(text)
                    elif "text" in item:
                        text = str(item["text"])
                        if text.strip():
                            texts.append(text)
                elif isinstance(item, str) and item.strip():
                    texts.append(item)
            result = "".join(texts)
            return result if result.strip() else None
        else:
            text = str(content)
            return text if text.strip() else None
    return None


def extract_tool_info(node_name: str, node_data: dict) -> str:
    """
    Extract human-readable tool information from LangGraph node data.

    Identifies which tool is being executed and returns a formatted string
    describing the action. Checks multiple sources:
    1. Direct node name match with TOOL_NAMES
    2. Tool calls within node_data messages
    3. Tool name patterns in node_name

    Args:
        node_name: Name of the LangGraph node being executed.
        node_data: Dictionary containing node execution data, may include
                   'messages' key with tool call information.

    Returns:
        Formatted string in the format "{tool_name}:: {action_description}" if a
        recognized tool is found, None otherwise.

        Recognized tools and their descriptions:
        - categorize_transaction: "trying to categorize transaction"
        - create_budget_rule: "creating budget rule"
        - save_user_profile: "saving user profile"

    Example:
        >>> extract_tool_info("categorize_transaction", {})
        'categorize_transaction:: trying to categorize transaction'

        >>> extract_tool_info("some_node", {"messages": [{"tool_calls": [{"name": "create_budget_rule"}]}]})
        'create_budget_rule:: creating budget rule'
    """
    if node_name in TOOL_NAMES:
        action_map = {
            "categorize_transaction": "trying to categorize transaction",
            "create_budget_rule": "creating budget rule",
            "save_user_profile": "saving user profile",
        }
        return f"{node_name}:: {action_map.get(node_name, 'processing')}"

    if "messages" in node_data:
        messages = node_data["messages"]
        for msg in messages:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tool_call in msg.tool_calls:
                    tool_name = (
                        tool_call.get("name", "")
                        if isinstance(tool_call, dict)
                        else getattr(tool_call, "name", "")
                    )
                    if tool_name in TOOL_NAMES:
                        action_map = {
                            "categorize_transaction": "trying to categorize transaction",
                            "create_budget_rule": "creating budget rule",
                            "save_user_profile": "saving user profile",
                        }
                        return (
                            f"{tool_name}:: {action_map.get(tool_name, 'processing')}"
                        )

    if "tools" in node_name.lower() or any(
        tool in node_name.lower() for tool in TOOL_NAMES
    ):
        for tool_name in TOOL_NAMES:
            if tool_name in node_name.lower():
                action_map = {
                    "categorize_transaction": "trying to categorize transaction",
                    "create_budget_rule": "creating budget rule",
                    "save_user_profile": "saving user profile",
                }
                return f"{tool_name}:: {action_map.get(tool_name, 'processing')}"

    return None


async def stream_agent_response(
    message: str, thread_id: str, user_id: str
) -> AsyncGenerator[str, None]:
    """
    Stream AI agent responses as Server-Sent Events (SSE).

    Sets up the user context, initializes the agent, and streams responses
    in real-time. Handles three types of events:
    - messages: Token-by-token text streaming from the agent
    - updates: Node updates for tool calls and execution status
    - custom: Custom events emitted by the agent

    The function yields SSE-formatted events that can be consumed by a client
    for real-time updates. Automatically manages database connections and
    handles errors gracefully.

    Args:
        message: User's input message to send to the AI agent.
        thread_id: Thread identifier for conversation continuity. If None or empty,
                   a new UUID will be generated.
        user_id: User identifier for setting context and authentication.

    Yields:
        SSE-formatted strings containing:
        - {"type": "text", "content": str}: Text chunks from the agent
        - {"type": "tool_update", "content": str}: Tool execution updates
        - {"type": "custom", "content": Any}: Custom events
        - {"type": "done", "data": {}}: Stream completion signal
        - {"type": "error", "data": {"message": str}}: Error information

    Raises:
        Any exceptions from the agent are caught and yielded as error events
        rather than being raised.

    Example:
        >>> async for event in stream_agent_response("Hello", "thread-123", "user-456"):
        ...     print(event)
        data: {"type": "text", "content": "Hello! How can I help?"}\\n\\n
        data: {"type": "done", "data": {}}\\n\\n

    Note:
        The database connection is automatically closed in the finally block.
        User context is set before streaming begins.
    """
    db = next(get_db())

    try:
        set_user_context(user_id, db)
        agent = get_agent()
        config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}

        async for event in agent.astream(
            {"messages": [("user", message)]},
            config=config,
            stream_mode=["updates", "custom", "messages"],
        ):
            if isinstance(event, tuple) and len(event) == 2:
                mode, data = event

                # Handle token-by-token streaming from messages mode
                if mode == "messages":
                    message_chunk, metadata = data
                    if hasattr(message_chunk, "content") and message_chunk.content:
                        yield format_sse_event(
                            {"type": "text", "content": message_chunk.content}
                        )

                # Handle node updates for tool calls
                elif mode == "updates" and isinstance(data, dict):
                    for node_name, node_data in data.items():
                        if not isinstance(node_data, dict):
                            continue

                        tool_info = extract_tool_info(node_name, node_data)
                        if tool_info:
                            yield format_sse_event(
                                {"type": "tool_update", "content": tool_info}
                            )

                # Handle custom events if you emit any
                elif mode == "custom":
                    yield format_sse_event({"type": "custom", "content": data})

        yield format_sse_event({"type": "done", "data": {}})
    except Exception as e:
        error_event = {"type": "error", "data": {"message": str(e)}}
        yield format_sse_event(error_event)
    finally:
        db.close()
