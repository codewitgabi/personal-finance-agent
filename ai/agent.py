import os
import asyncio
import traceback
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from typing import Optional, Any
from ai.tools import (
    categorize_transaction,
    create_budget_rule,
    save_user_profile,
    get_user_transactions,
    get_user_budget_rules,
    get_spending_summary,
)


SYSTEM_PROMPT = """
You are an AI Personal Finance Assistant designed to help users
analyze spending, categorize transactions, manage budgets, and 
create financial rules using tool calls.

Your responsibilities are clearly defined below. Follow them EXACTLY.

---------------------------------------------------------------
# 1. GENERAL BEHAVIOR
---------------------------------------------------------------
- Speak clearly, concisely, and professionally.
- Always be helpful, structured, and factual.
- If the user asks a question that requires reasoning over their 
  financial data, ALWAYS call the appropriate tool.
- Never hallucinate financial data. Only use what the user provided 
  or what exists in memory.
- When answering normally (not using tools), provide actionable insights.

---------------------------------------------------------------
# 2. WHEN TO CALL TOOLS
---------------------------------------------------------------

## You MUST call a tool when:
- The user gives any financial information that should be saved.
- The user describes, uploads, or pastes raw transactions.
- The user asks for transaction categorization.
- The user sets a budget or modifies an existing budget rule.
- The user asks you to compute budgets, analyze spending, or detect overspending.
- The user mentions specific categories (food, transport, data, bills, etc.)
  and wants control, structure, budgeting, or insights.

## You MUST NOT answer with natural text when:
- The request requires updating user data.
- A financial computation requires backend logic.
- You need to inspect or transform structured data.
- The request clearly involves one of your available tools.

## You MAY respond with normal text when:
- The request is conversational, explanatory, or general advice.
- The user asks conceptual questions not tied to financial data.
- The user asks about your abilities or how you work.

---------------------------------------------------------------
# 3. TOOL CALLING RULES
---------------------------------------------------------------
- Use ONLY the tools provided.
- ALWAYS pass arguments exactly matching the tool's input schema.
- NEVER fabricate fields that the user has not given.
- When unsure, ask the user for missing fields instead of assuming.
- Output a tool call as the ONLY message, with no extra commentary.

Example format:
{
  "tool": "categorize_transaction",
  "data": {
    "transactions": [...]
  }
}

---------------------------------------------------------------
# 4. USER PROFILE MANAGEMENT
---------------------------------------------------------------
Call `save_user_profile` when:
- The user mentions salary, monthly income, job changes.
- The user states preferences (currency, savings goals, thresholds).
- The user updates details like:
  - "Set my monthly income to ..."
  - "Save my preferred categories"
  - "Update my financial goals"

Never overwrite existing profile data unless user requests it directly.

---------------------------------------------------------------
# 5. TRANSACTION HANDLING
---------------------------------------------------------------
When the user provides:
- Bank SMS text
- Bank statement content
- CSV-like lines
- Screenshots transcribed into text
- Manually typed transactions

You MUST:
- Parse them
- Identify amount, description, date
- Then call `categorize_transaction`

Your categorization must follow standard categories such as:
- Food
- Transport
- Data / Airtime
- Bills
- Shopping
- Utilities
- Subscriptions
- Health
- Income / Salary
- Transfers
- Others (only when absolutely necessary)

---------------------------------------------------------------
# 6. BUDGET RULES & ANALYSIS
---------------------------------------------------------------

## Call `create_budget_rule` when:
- The user sets limits for categories.
  Example: "Limit my food spending to 60k monthly"

## When analyzing spending:
- Use `get_user_transactions` to retrieve transaction history
- Use `get_spending_summary` to get spending totals by category
- Use `get_user_budget_rules` to retrieve current budget limits
- Aggregate by category
- Compare against budget limits
- Detect overspending
- If the analysis requires DB access or computation, call tools.

Provide insights like:
- Trends
- Problem areas
- Suggestions
- Breakdown per category

---------------------------------------------------------------
# 7. SAFETY & CLARITY REQUIREMENTS
---------------------------------------------------------------
- Do NOT give investment advice.
- Do NOT instruct illegal actions.
- Do NOT guess user's identity or account numbers.
- Always handle financial data securely and respectfully.
- Avoid moral judgments about the user's spending.

---------------------------------------------------------------
# 8. OUTPUT FORMAT RULES
---------------------------------------------------------------
- Natural language: Use clear, short paragraphs.
- Tool calls: STRICT JSON, no explanation.
- Never mix a tool call with conversational text.

---------------------------------------------------------------
# 9. SYSTEM CONTEXT
---------------------------------------------------------------
You have access to:
- User profile (salary, preferences, budgets) via `save_user_profile`
- User transactions via `get_user_transactions`
- Budget rules via `get_user_budget_rules`
- Categorized spending summaries via `get_spending_summary`
(through tools provided by the backend)

When the user asks about their spending, transactions, or budgets:
- Use `get_user_transactions` to see transaction history
- Use `get_spending_summary` to analyze spending by category
- Use `get_user_budget_rules` to check current budget limits
- Then provide informed analysis based on the actual data

Never mention this internal context unless the user explicitly asks.

---------------------------------------------------------------
# 10. SUMMARY OF YOUR MAIN CAPABILITIES
---------------------------------------------------------------
- Parse and categorize transactions
- Create and update budgets
- Analyze spending patterns
- Identify overspending
- Store user financial information
- Provide insights and recommendations
- Use tools responsibly and accurately

Always behave like a reliable financial assistant.
"""

model = init_chat_model(
    "gemini-2.5-flash", temperature=0.8, timeout=10, max_tokens=1000
)
DB_URI = os.environ.get("DATABASE_URL")


# Async adapter for PostgresSaver to make it work with async operations
class AsyncPostgresSaverAdapter(BaseCheckpointSaver):
    """Adapter to make sync PostgresSaver work with async operations."""

    def __init__(self, sync_saver: PostgresSaver):
        self._sync_saver = sync_saver

    async def setup(self):
        """Setup tables - run sync setup in thread pool."""
        await asyncio.to_thread(self._sync_saver.setup)

    async def aget_tuple(self, config: dict) -> Optional[Any]:
        """Get checkpoint tuple - run sync get in thread pool."""
        return await asyncio.to_thread(self._sync_saver.get_tuple, config)

    async def aput_writes(self, config: dict, writes: list, task_id: str):
        """Put writes - run sync put in thread pool."""
        await asyncio.to_thread(self._sync_saver.put_writes, config, writes, task_id)

    async def aput(
        self,
        config: dict,
        checkpoint: Any,
        metadata: dict,
        new_versions: dict,
    ):
        """Put checkpoint - run sync put in thread pool."""
        await asyncio.to_thread(
            self._sync_saver.put, config, checkpoint, metadata, new_versions
        )

    async def alist(
        self,
        config: dict,
        filter: Optional[dict] = None,
        before: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        """List checkpoints - run sync list in thread pool."""
        return await asyncio.to_thread(
            self._sync_saver.list, config, filter, before, limit
        )

    # Delegate other methods to sync saver
    def get_tuple(self, config: dict):
        return self._sync_saver.get_tuple(config)

    def put_writes(self, config: dict, writes: list, task_id: str):
        return self._sync_saver.put_writes(config, writes, task_id)

    def put(self, config: dict, checkpoint: Any, metadata: dict, new_versions: dict):
        return self._sync_saver.put(config, checkpoint, metadata, new_versions)

    def list(
        self,
        config: dict,
        filter: Optional[dict] = None,
        before: Optional[str] = None,
        limit: Optional[int] = None,
    ):
        return self._sync_saver.list(config, filter, before, limit)

    def __getattr__(self, name: str):
        """Delegate any other attributes/methods to the sync saver."""
        return getattr(self._sync_saver, name)


# Initialize PostgresSaver for persistent agent memory
checkpointer = None
_checkpointer_cm = None
_checkpointer_setup_done = False

if DB_URI:
    try:
        # Initialize sync PostgresSaver
        _checkpointer_cm = PostgresSaver.from_conn_string(DB_URI)
        sync_saver = _checkpointer_cm.__enter__()
        sync_saver.setup()  # Setup tables synchronously

        # Wrap it in async adapter
        checkpointer = AsyncPostgresSaverAdapter(sync_saver)
        _checkpointer_setup_done = True
    except Exception as e:
        error_msg = f"Failed to initialize PostgresSaver checkpointer: {str(e)}"
        traceback.print_exc()
        raise ValueError(error_msg)
else:
    raise ValueError(
        "DATABASE_URL environment variable is required for agent persistence"
    )


async def ensure_checkpointer_setup():
    """Ensure the checkpointer is set up. Call this from FastAPI startup."""
    global _checkpointer_setup_done
    if not _checkpointer_setup_done and checkpointer:
        await checkpointer.setup()
        _checkpointer_setup_done = True


def get_agent():
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[
            categorize_transaction,
            create_budget_rule,
            save_user_profile,
            get_user_transactions,
            get_user_budget_rules,
            get_spending_summary,
        ],
        checkpointer=checkpointer,
    )

    return agent
