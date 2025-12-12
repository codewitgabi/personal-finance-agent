import re
from decimal import Decimal
from typing import Optional
from sqlalchemy.orm import Session
from langchain.tools import tool
from api.v1.services.transaction_service import transaction_service
from api.v1.services.budget_service import budget_service
from api.v1.models.budget_rule import BudgetPeriod
from api.v1.services.user import user_service
from api.v1.models.transaction import TransactionType, TransactionSource
from api.v1.utils.database import SessionLocal
from api.v1.utils.logger import get_logger
from langgraph.config import get_stream_writer

logger = get_logger("ai_tools")

_user_context = {}
_db_session = None
_external_db_session = None  # Track if session was passed from outside


def set_user_context(user_id: str, db: Session = None):
    global _user_context, _db_session, _external_db_session
    _user_context["user_id"] = user_id
    _external_db_session = db  # Track if session was passed from outside
    _db_session = db or SessionLocal()


def get_db_session():
    global _db_session
    if _db_session is None:
        _db_session = SessionLocal()
    return _db_session


def parse_transaction_text(text: str) -> dict:
    amount_pattern = r"[\d,]+\.?\d*"
    currency_pattern = r"[A-Z]{3}|USD|NGN|EUR|GBP"

    amounts = re.findall(amount_pattern, text.replace(",", ""))
    amount = None
    if amounts:
        try:
            amount = Decimal(amounts[0])
        except:
            pass

    transaction_type = TransactionType.DEBIT
    if any(
        word in text.lower()
        for word in ["credit", "received", "deposit", "salary", "income"]
    ):
        transaction_type = TransactionType.CREDIT

    return {
        "amount": amount,
        "type": transaction_type,
        "description": text.strip(),
    }


@tool
def categorize_transaction(transaction: str) -> str:
    """
    Categorize a transaction and save it to the database.
    Parse the transaction text to extract amount, description, and type.
    Then categorize it and store it.

    Args:
        transaction: The transaction text to parse and categorize (e.g., "Spent 5000 on food", "Received 100000 salary")

    Returns:
        A message confirming the transaction was categorized and saved.
    """
    writer = get_stream_writer()
    writer(f"Starting transaction categorization for: {transaction}")

    if "user_id" not in _user_context:
        return "Error: User context not set. Please authenticate first."

    db = get_db_session()
    user_id = _user_context["user_id"]

    try:
        writer("Parsing transaction text to extract amount, type, and description")

        parsed = parse_transaction_text(transaction)

        if not parsed["amount"]:
            writer("Error: Could not extract amount from transaction text")
            return "Error: Could not extract amount from transaction text."

        writer(
            f"Parsed transaction - Amount: {parsed['amount']}, Type: {parsed['type'].value}"
        )

        category_map = {
            "food": [
                "food",
                "restaurant",
                "cafe",
                "meal",
                "eat",
                "lunch",
                "dinner",
                "breakfast",
            ],
            "transport": ["transport", "uber", "taxi", "bus", "fuel", "gas", "petrol"],
            "data / airtime": [
                "data",
                "airtime",
                "mobile",
                "phone",
                "internet",
                "data bundle",
            ],
            "bills": ["bill", "electricity", "water", "utility"],
            "shopping": ["shop", "store", "mall", "purchase", "buy"],
            "utilities": ["utility", "internet", "wifi", "cable"],
            "subscriptions": ["subscription", "netflix", "spotify", "premium"],
            "health": ["health", "hospital", "pharmacy", "medicine", "doctor"],
            "income / salary": ["salary", "income", "pay", "wage", "received"],
            "transfers": ["transfer", "sent", "received"],
        }

        writer("Categorizing transaction based on keywords")

        transaction_lower = transaction.lower()
        category = "Others"
        confidence = Decimal("0.5")

        for cat, keywords in category_map.items():
            if any(keyword in transaction_lower for keyword in keywords):
                category = cat
                confidence = Decimal("0.9")
                break

        writer(f"Transaction categorized as '{category}' with confidence {confidence}")
        writer("Saving transaction to database")

        transaction_service.create_transaction(
            user_id=user_id,
            amount=parsed["amount"],
            transaction_type=parsed["type"],
            source=TransactionSource.MANUAL,
            ai_category=category,
            ai_confidence=confidence,
            db=db,
        )

        writer("Transaction saved successfully")

        return f"Transaction categorized as '{category}' and saved successfully. Amount: {parsed['amount']}, Type: {parsed['type'].value}"

    except Exception as e:
        logger.error(
            "Error categorizing transaction", extra={"error": str(e)}, exc_info=True
        )
        return f"Error processing transaction: {str(e)}"
    finally:
        global _db_session, _external_db_session
        # Only close the session if we created it ourselves (not passed from outside)
        if _db_session and _db_session is not _external_db_session:
            _db_session.close()
            _db_session = None


@tool
def create_budget_rule(limit_amount: float, period: str) -> str:
    """
    Create a budget rule with a limit amount and period.

    Args:
        limit_amount: The spending limit amount (e.g., 60000.0)
        period: The period for the budget rule - must be one of: "daily", "weekly", "monthly"

    Returns:
        A message confirming the budget rule was created.
    """
    writer = get_stream_writer()
    writer(f"Creating budget rule - Limit: {limit_amount}, Period: {period}")

    if "user_id" not in _user_context:
        return "Error: User context not set. Please authenticate first."

    db = get_db_session()
    user_id = _user_context["user_id"]

    try:
        writer(f"Validating period: {period}")

        period_upper = period.upper()
        if period_upper not in ["DAILY", "WEEKLY", "MONTHLY"]:
            writer(
                f"Error: Invalid period '{period}'. Must be 'daily', 'weekly', or 'monthly'"
            )
            return (
                f"Error: Period must be 'daily', 'weekly', or 'monthly'. Got: {period}"
            )

        budget_period = BudgetPeriod[period_upper]

        writer(
            f"Creating budget rule in database with limit {limit_amount} for {period} period"
        )

        budget_rule = budget_service.create_budget_rule(
            user_id=user_id,
            limit_amount=Decimal(str(limit_amount)),
            period=budget_period,
            db=db,
        )

        writer(
            f"Budget rule created successfully. Next reset: {budget_rule.next_reset_date}"
        )

        return f"Budget rule created successfully. Limit: {limit_amount} {period}. Next reset: {budget_rule.next_reset_date}"

    except Exception as e:
        logger.error(
            "Error creating budget rule", extra={"error": str(e)}, exc_info=True
        )
        return f"Error creating budget rule: {str(e)}"
    finally:
        global _db_session, _external_db_session
        # Only close the session if we created it ourselves (not passed from outside)
        if _db_session and _db_session is not _external_db_session:
            _db_session.close()
            _db_session = None


@tool
def save_user_profile(
    monthly_income: Optional[float] = None,
    savings_goal: Optional[float] = None,
    currency: Optional[str] = None,
) -> str:
    """
    Save or update user profile information.

    Args:
        monthly_income: The user's monthly income (optional)
        savings_goal: The user's savings goal amount (optional)
        currency: The user's preferred currency code, e.g., "USD", "NGN" (optional)

    Returns:
        A message confirming the profile was updated.
    """
    writer = get_stream_writer()
    updates_list = []
    if monthly_income:
        updates_list.append(f"monthly income: {monthly_income}")
    if savings_goal:
        updates_list.append(f"savings goal: {savings_goal}")
    if currency:
        updates_list.append(f"currency: {currency}")

    writer(
        f"Updating user profile with: {', '.join(updates_list) if updates_list else 'no updates'}"
    )

    if "user_id" not in _user_context:
        return "Error: User context not set. Please authenticate first."

    db = get_db_session()
    user_id = _user_context["user_id"]

    try:
        writer("Saving profile updates to database")

        user = user_service.update_user_profile(
            user_id=user_id,
            monthly_income=Decimal(str(monthly_income)) if monthly_income else None,
            savings_goal=Decimal(str(savings_goal)) if savings_goal else None,
            currency=currency,
            db=db,
        )

        if not user:
            writer("Error: User not found")
            return "Error: User not found."

        updates = []
        if monthly_income:
            updates.append(f"monthly income: {monthly_income}")
        if savings_goal:
            updates.append(f"savings goal: {savings_goal}")
        if currency:
            updates.append(f"currency: {currency}")

        writer(f"User profile updated successfully: {', '.join(updates)}")

        return f"User profile updated successfully. Updated: {', '.join(updates)}"

    except Exception as e:
        logger.error(
            "Error saving user profile", extra={"error": str(e)}, exc_info=True
        )
        return f"Error updating profile: {str(e)}"
    finally:
        global _db_session, _external_db_session
        # Only close the session if we created it ourselves (not passed from outside)
        if _db_session and _db_session is not _external_db_session:
            _db_session.close()
            _db_session = None


@tool
def get_user_transactions(limit: Optional[int] = 10) -> str:
    """
    Retrieve the user's transaction history from the database.

    Args:
        limit: Optional number of transactions to return (default: 10). Use a higher number for more history.

    Returns:
        A formatted summary of recent transactions with amounts, categories, types, and dates.
    """
    writer = get_stream_writer()
    writer(f"Retrieving user transactions (limit: {limit})")

    if "user_id" not in _user_context:
        return "Error: User context not set. Please authenticate first."

    db = get_db_session()
    user_id = _user_context["user_id"]

    try:
        writer("Fetching transactions from database")
        transactions = transaction_service.get_user_transactions(
            user_id=user_id, db=db, limit=limit
        )

        if not transactions:
            writer("No transactions found")
            return "No transactions found in your history."

        writer(f"Found {len(transactions)} transactions")

        result_lines = [f"Transaction History ({len(transactions)} transactions):\n"]
        for i, txn in enumerate(transactions, 1):
            category = txn.ai_category or "Uncategorized"
            date_str = (
                txn.created_at.strftime("%Y-%m-%d %H:%M")
                if txn.created_at
                else "Unknown date"
            )
            result_lines.append(
                f"{i}. {txn.type.value.upper()}: {txn.amount} - {category} ({date_str})"
            )

        result = "\n".join(result_lines)
        writer("Transactions retrieved successfully")
        return result

    except Exception as e:
        logger.error(
            "Error retrieving transactions", extra={"error": str(e)}, exc_info=True
        )
        return f"Error retrieving transactions: {str(e)}"
    finally:
        global _db_session, _external_db_session
        # Only close the session if we created it ourselves (not passed from outside)
        if _db_session and _db_session is not _external_db_session:
            _db_session.close()
            _db_session = None


@tool
def get_user_budget_rules() -> str:
    """
    Retrieve the user's budget rules from the database.

    Returns:
        A formatted list of all budget rules with limits, periods, and next reset dates.
    """
    writer = get_stream_writer()
    writer("Retrieving user budget rules")

    if "user_id" not in _user_context:
        return "Error: User context not set. Please authenticate first."

    db = get_db_session()
    user_id = _user_context["user_id"]

    try:
        writer("Fetching budget rules from database")
        budget_rules = budget_service.get_user_budget_rules(user_id=user_id, db=db)

        if not budget_rules:
            writer("No budget rules found")
            return "No budget rules found. You can create one using the create_budget_rule tool."

        writer(f"Found {len(budget_rules)} budget rules")

        result_lines = [f"Budget Rules ({len(budget_rules)} active):\n"]
        for i, rule in enumerate(budget_rules, 1):
            reset_date_str = (
                rule.next_reset_date.strftime("%Y-%m-%d")
                if rule.next_reset_date
                else "Unknown"
            )
            result_lines.append(
                f"{i}. Limit: {rule.limit_amount} per {rule.period.value} | Next reset: {reset_date_str}"
            )

        result = "\n".join(result_lines)
        writer("Budget rules retrieved successfully")
        return result

    except Exception as e:
        logger.error(
            "Error retrieving budget rules", extra={"error": str(e)}, exc_info=True
        )
        return f"Error retrieving budget rules: {str(e)}"
    finally:
        global _db_session, _external_db_session
        # Only close the session if we created it ourselves (not passed from outside)
        if _db_session and _db_session is not _external_db_session:
            _db_session.close()
            _db_session = None


@tool
def get_spending_summary() -> str:
    """
    Get a summary of spending totals grouped by category.

    Returns:
        A formatted summary showing total spending per category for debit transactions.
    """
    writer = get_stream_writer()
    writer("Retrieving spending summary by category")

    if "user_id" not in _user_context:
        return "Error: User context not set. Please authenticate first."

    db = get_db_session()
    user_id = _user_context["user_id"]

    try:
        writer("Calculating spending summary from database")
        summary = transaction_service.get_spending_summary(user_id=user_id, db=db)

        if not summary:
            writer("No spending data found")
            return "No spending data found. No transactions have been categorized yet."

        writer(f"Found spending data for {len(summary)} categories")

        result_lines = ["Spending Summary by Category:\n"]
        total_spending = sum(summary.values())
        for category, amount in sorted(
            summary.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (amount / total_spending * 100) if total_spending > 0 else 0
            result_lines.append(f"- {category}: {amount} ({percentage:.1f}%)")

        result_lines.append(f"\nTotal Spending: {total_spending}")
        result = "\n".join(result_lines)
        writer("Spending summary retrieved successfully")
        return result

    except Exception as e:
        logger.error(
            "Error retrieving spending summary", extra={"error": str(e)}, exc_info=True
        )
        return f"Error retrieving spending summary: {str(e)}"
    finally:
        global _db_session, _external_db_session
        # Only close the session if we created it ourselves (not passed from outside)
        if _db_session and _db_session is not _external_db_session:
            _db_session.close()
            _db_session = None


TOOL_NAMES = [
    "categorize_transaction",
    "create_budget_rule",
    "save_user_profile",
    "get_user_transactions",
    "get_user_budget_rules",
    "get_spending_summary",
]
