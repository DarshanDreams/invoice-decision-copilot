import os
from typing import Dict, Any


def get_gemini_api_key():
    """
    Supports both:
    1. Local environment variable: GEMINI_API_KEY
    2. Streamlit secrets: GEMINI_API_KEY
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if api_key:
        return api_key

    try:
        import streamlit as st
        return st.secrets.get("GEMINI_API_KEY")
    except Exception:
        return None


def generate_ai_explanation(
    parsed_invoice: Dict[str, Any],
    po_match_result: Dict[str, Any],
    decision_result: Dict[str, Any]
) -> str:
    """
    Optional Gemini-based business explanation.

    If Gemini is not configured, the app still works using the deterministic
    rule-based decision engine.
    """

    api_key = get_gemini_api_key()

    if not api_key:
        return (
            "AI explanation is not configured because GEMINI_API_KEY is missing. "
            "The decision above was generated using deterministic AP business rules, "
            "including PO matching, duplicate detection, vendor validation, and amount tolerance checks."
        )

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        prompt = f"""
You are an Accounts Payable automation assistant.

Explain the invoice decision below to a non-technical AP manager.

Keep the explanation:
- short
- business-friendly
- audit-ready
- clear about why the invoice was approved, rejected, or sent for review

Parsed Invoice:
{parsed_invoice}

PO Match Result:
{po_match_result}

Decision Result:
{decision_result}

Return only the explanation.
"""

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        return response.text

    except Exception as e:
        return (
            "AI explanation could not be generated. "
            f"The rule-based decision is still valid. Error: {str(e)}"
        )