import json
import uuid
import time
from typing import AsyncGenerator, Any, Optional
from langchain_core.messages import HumanMessage
from ai.agent import get_agent, model
from ai.tools import set_user_context, TOOL_NAMES
from api.v1.utils.dependencies import get_db
from api.v1.services.chat_message_service import chat_message_service
from api.v1.services.conversation_service import conversation_service
from api.v1.models.chat_message import MessageRole, MessageStatus, FinishReason

# Model identifier - should match the model in ai/agent.py
MODEL_NAME = "gemini-2.5-flash"
MODEL_TEMPERATURE = 0.8


async def generate_conversation_title(user_message: str, assistant_message: str) -> str:
    """
    Generate a conversation title using the AI model based on the first exchange.

    Args:
        user_message: First user message in the conversation
        assistant_message: First assistant response

    Returns:
        Generated title string
    """
    try:
        title_prompt = f"""Based on this conversation exchange, generate a concise title (max 6 words) that summarizes the topic:

User: {user_message[:200]}
Assistant: {assistant_message[:200]}

Title:"""

        response = await model.ainvoke([HumanMessage(content=title_prompt)])

        # Extract title from response
        if hasattr(response, "content"):
            title = response.content
        elif isinstance(response, str):
            title = response
        else:
            title = str(response)

        # Clean up the title
        title = title.strip()
        # Remove quotes if present
        if title.startswith('"') and title.endswith('"'):
            title = title[1:-1]
        if title.startswith("'") and title.endswith("'"):
            title = title[1:-1]

        # Remove "Title:" prefix if present
        if title.lower().startswith("title:"):
            title = title[6:].strip()

        # Limit to 200 characters
        if len(title) > 200:
            title = title[:197] + "..."

        return title if title else "New Conversation"
    except Exception as e:
        # Fallback to a simple title if generation fails
        words = user_message.split()[:6]
        return " ".join(words) if words else "New Conversation"


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
    Stream AI agent responses as Server-Sent Events (SSE) and save messages to database.

    Sets up the user context, initializes the agent, and streams responses
    in real-time. Handles three types of events:
    - messages: Token-by-token text streaming from the agent
    - updates: Node updates for tool calls and execution status
    - custom: Custom events emitted by the agent

    The function yields SSE-formatted events that can be consumed by a client
    for real-time updates. Automatically manages database connections and
    handles errors gracefully. All messages are saved to the database.

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
        Messages are saved to the database during streaming.
    """
    db = next(get_db())
    start_time = time.time()
    user_message_id: Optional[str] = None
    assistant_message_id: Optional[str] = None
    assistant_content = ""
    tool_calls = []
    final_thread_id = thread_id or str(uuid.uuid4())
    conversation = None
    conversation_id: Optional[str] = None
    is_new_conversation = False

    try:
        # Get or create conversation
        if thread_id:
            conversation = conversation_service.get_conversation_by_thread_id(
                user_id=user_id, thread_id=thread_id, db=db
            )

        if not conversation:
            # Create new conversation
            is_new_conversation = True
            conversation = conversation_service.create_conversation(
                user_id=user_id,
                thread_id=final_thread_id,
                title=None,  # Will be generated after first exchange
                db=db,
            )

        # Store conversation_id to avoid detached object issues
        conversation_id = conversation.id

        # Save user message
        user_message = chat_message_service.create_message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=message,
            model=MODEL_NAME,
            temperature=MODEL_TEMPERATURE,
            status=MessageStatus.COMPLETED,
            db=db,
        )
        user_message_id = user_message.id

        set_user_context(user_id, db)
        agent = get_agent()
        config = {"configurable": {"thread_id": final_thread_id}}

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
                        # Extract text content
                        chunk_text = extract_text_from_message(message_chunk)
                        if chunk_text:
                            assistant_content += chunk_text

                            # Create assistant message if it doesn't exist
                            if assistant_message_id is None:
                                assistant_message = chat_message_service.create_message(
                                    conversation_id=conversation_id,
                                    role=MessageRole.ASSISTANT,
                                    content=assistant_content,
                                    parent_message_id=user_message_id,
                                    model=MODEL_NAME,
                                    temperature=MODEL_TEMPERATURE,
                                    status=MessageStatus.PENDING,
                                    db=db,
                                )
                                assistant_message_id = assistant_message.id
                            else:
                                # Update existing message with accumulated content
                                chat_message_service.update_message(
                                    message_id=assistant_message_id,
                                    content=assistant_content,
                                    db=db,
                                )

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
                            # Track tool calls for metadata
                            tool_calls.append({"node": node_name, "info": tool_info})
                            yield format_sse_event(
                                {"type": "tool_update", "content": tool_info}
                            )

                # Handle custom events if you emit any
                elif mode == "custom":
                    yield format_sse_event({"type": "custom", "content": data})

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        # Finalize assistant message
        if assistant_message_id:
            # Token usage would need to be extracted from response metadata
            # For now, set to None as LangChain streaming doesn't expose this directly
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None

            # Prepare metadata
            message_metadata = {}
            if tool_calls:
                message_metadata["tool_calls"] = tool_calls

            chat_message_service.update_message(
                message_id=assistant_message_id,
                status=MessageStatus.COMPLETED,
                finish_reason=FinishReason.STOP,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                message_metadata=message_metadata if message_metadata else None,
                db=db,
            )
        elif assistant_content:
            # Create assistant message if we have content but no message yet
            chat_message_service.create_message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=assistant_content,
                parent_message_id=user_message_id,
                model=MODEL_NAME,
                temperature=MODEL_TEMPERATURE,
                status=MessageStatus.COMPLETED,
                finish_reason=FinishReason.STOP,
                latency_ms=latency_ms,
                message_metadata={"tool_calls": tool_calls} if tool_calls else None,
                db=db,
            )

        # Generate title for new conversations after first exchange
        if is_new_conversation and assistant_content:
            # Reload conversation to ensure it's bound to the session
            conversation = conversation_service.get_conversation_by_id(
                conversation_id=conversation_id, user_id=user_id, db=db
            )
            if conversation and not conversation.title:
                try:
                    title = await generate_conversation_title(
                        message, assistant_content
                    )
                    conversation_service.update_conversation_title(
                        conversation_id=conversation_id, title=title, db=db
                    )
                except Exception as e:
                    # If title generation fails, use fallback
                    words = message.split()[:6]
                    fallback_title = " ".join(words) if words else "New Conversation"
                    conversation_service.update_conversation_title(
                        conversation_id=conversation_id, title=fallback_title, db=db
                    )

        # Reload conversation to get the latest title and thread_id for the response
        conversation = conversation_service.get_conversation_by_id(
            conversation_id=conversation_id, user_id=user_id, db=db
        )
        conversation_title = conversation.title if conversation else None
        conversation_thread_id = (
            conversation.thread_id if conversation else final_thread_id
        )

        yield format_sse_event(
            {
                "type": "done",
                "data": {
                    "thread_id": conversation_thread_id,
                    "title": conversation_title or "New Conversation",
                },
            }
        )
    except Exception as e:
        # Update assistant message status to error if it exists
        if assistant_message_id:
            try:
                chat_message_service.update_message(
                    message_id=assistant_message_id,
                    status=MessageStatus.ERROR,
                    finish_reason=FinishReason.ERROR,
                    message_metadata={"error": str(e)},
                    db=db,
                )
            except:
                pass  # Don't fail if update fails

        # Try to get conversation info for error response
        error_data = {"message": str(e)}
        if conversation_id:
            try:
                conversation = conversation_service.get_conversation_by_id(
                    conversation_id=conversation_id, user_id=user_id, db=db
                )
                if conversation:
                    error_data["thread_id"] = conversation.thread_id
                    error_data["title"] = conversation.title or "New Conversation"
                else:
                    error_data["thread_id"] = final_thread_id
                    error_data["title"] = "New Conversation"
            except:
                # If we can't get conversation, at least include thread_id
                error_data["thread_id"] = final_thread_id
                error_data["title"] = "New Conversation"
        else:
            error_data["thread_id"] = final_thread_id
            error_data["title"] = "New Conversation"

        error_event = {"type": "error", "data": error_data}
        yield format_sse_event(error_event)
    finally:
        db.close()
