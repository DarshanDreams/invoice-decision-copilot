from typing import Dict, Any, List
import pandas as pd
from rapidfuzz import fuzz


def safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def normalize_text(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def calculate_amount_context(po_record: Dict[str, Any], invoice_total: float | None) -> Dict[str, Any]:
    """
    Calculate PO amount, tolerance, max allowed amount, already invoiced amount,
    and remaining allowed balance.
    """

    po_amount = safe_float(po_record.get("po_amount"))
    tolerance_percent = safe_float(po_record.get("tolerance_percent"))
    already_invoiced_amount = safe_float(po_record.get("already_invoiced_amount"))

    max_allowed_amount = po_amount * (1 + tolerance_percent / 100)
    remaining_allowed_amount = max_allowed_amount - already_invoiced_amount

    amount_within_remaining_balance = False

    if invoice_total is not None:
        amount_within_remaining_balance = invoice_total <= remaining_allowed_amount

    return {
        "po_amount": po_amount,
        "tolerance_percent": tolerance_percent,
        "max_allowed_amount": round(max_allowed_amount, 2),
        "already_invoiced_amount": already_invoiced_amount,
        "remaining_allowed_amount": round(remaining_allowed_amount, 2),
        "invoice_total": invoice_total,
        "amount_within_remaining_balance": amount_within_remaining_balance
    }


def score_amount_match(po_record: Dict[str, Any], invoice_total: float | None) -> float:
    """
    Score how well invoice amount fits the PO remaining amount.
    100 = invoice amount is within remaining balance
    lower score = invoice amount is far away or missing
    """

    if invoice_total is None:
        return 0.0

    amount_context = calculate_amount_context(po_record, invoice_total)
    remaining = amount_context["remaining_allowed_amount"]

    if invoice_total <= remaining:
        return 100.0

    if remaining <= 0:
        return 0.0

    difference_ratio = abs(invoice_total - remaining) / remaining

    if difference_ratio <= 0.05:
        return 85.0
    elif difference_ratio <= 0.15:
        return 60.0
    elif difference_ratio <= 0.30:
        return 35.0
    else:
        return 10.0


def build_candidate_score(
    parsed_invoice: Dict[str, Any],
    po_record: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Build a candidate PO score when invoice PO number is missing.
    We use:
    - vendor similarity
    - amount fit
    - description similarity
    """

    invoice_vendor = normalize_text(parsed_invoice.get("vendor_name"))
    invoice_description = normalize_text(parsed_invoice.get("description"))

    po_vendor = normalize_text(po_record.get("vendor_name"))
    po_description = normalize_text(po_record.get("description"))

    vendor_score = fuzz.token_sort_ratio(invoice_vendor, po_vendor)
    description_score = fuzz.token_set_ratio(invoice_description, po_description)
    amount_score = score_amount_match(po_record, parsed_invoice.get("total_amount"))

    # Weighted score
    # Vendor is strongest, amount is second, description is third.
    overall_score = round(
        (vendor_score * 0.50) +
        (amount_score * 0.30) +
        (description_score * 0.20),
        2
    )

    amount_context = calculate_amount_context(
        po_record,
        parsed_invoice.get("total_amount")
    )

    return {
        "po_number": po_record.get("po_number"),
        "vendor_name": po_record.get("vendor_name"),
        "vendor_status": po_record.get("vendor_status"),
        "po_amount": po_record.get("po_amount"),
        "description": po_record.get("description"),
        "vendor_score": round(vendor_score, 2),
        "amount_score": round(amount_score, 2),
        "description_score": round(description_score, 2),
        "overall_score": overall_score,
        "remaining_allowed_amount": amount_context["remaining_allowed_amount"]
    }


def match_invoice_to_po(
    parsed_invoice: Dict[str, Any],
    po_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Match parsed invoice fields against purchase order database.

    Handles:
    1. Exact PO match when PO number exists
    2. Missing PO inference using vendor + amount + description
    3. No reliable match
    """

    po_number = parsed_invoice.get("po_number")
    invoice_total = parsed_invoice.get("total_amount")

    result = {
        "po_found": False,
        "match_type": "NO_MATCH",
        "matched_po_number": None,
        "match_score": 0.0,
        "po_record": None,
        "amount_context": None,
        "candidate_pos": [],
        "explanation": [],
        "warnings": []
    }

    # CASE 1: Explicit PO number exists in invoice
    if po_number:
        exact_matches = po_df[
            po_df["po_number"].astype(str).str.upper() == str(po_number).upper()
        ]

        if not exact_matches.empty:
            po_record = exact_matches.iloc[0].to_dict()
            amount_context = calculate_amount_context(po_record, invoice_total)

            result.update({
                "po_found": True,
                "match_type": "EXACT_PO_MATCH",
                "matched_po_number": po_record.get("po_number"),
                "match_score": 100.0,
                "po_record": po_record,
                "amount_context": amount_context,
                "explanation": [
                    f"Invoice explicitly references PO {po_record.get('po_number')}.",
                    f"Matched vendor in PO database: {po_record.get('vendor_name')}.",
                    f"PO amount is {po_record.get('currency')} {amount_context['po_amount']:,.2f}.",
                    f"Tolerance is {amount_context['tolerance_percent']}%, so max allowed amount is {po_record.get('currency')} {amount_context['max_allowed_amount']:,.2f}.",
                    f"Already invoiced amount is {po_record.get('currency')} {amount_context['already_invoiced_amount']:,.2f}.",
                    f"Remaining allowed amount is {po_record.get('currency')} {amount_context['remaining_allowed_amount']:,.2f}."
                ]
            })

            return result

        result["warnings"].append(
            f"Invoice references PO {po_number}, but this PO was not found in the PO database."
        )

    # CASE 2: PO missing or invalid — infer candidate PO
    candidates: List[Dict[str, Any]] = []

    for _, row in po_df.iterrows():
        po_record = row.to_dict()
        candidate = build_candidate_score(parsed_invoice, po_record)
        candidates.append(candidate)

    candidates = sorted(
        candidates,
        key=lambda item: item["overall_score"],
        reverse=True
    )

    top_candidates = candidates[:3]
    result["candidate_pos"] = top_candidates

    if top_candidates:
        best_candidate = top_candidates[0]

        # Strong enough to suggest, but not auto-approve.
        if best_candidate["overall_score"] >= 75:
            matched_po = po_df[
                po_df["po_number"].astype(str) == str(best_candidate["po_number"])
            ].iloc[0].to_dict()

            amount_context = calculate_amount_context(matched_po, invoice_total)

            result.update({
                "po_found": True,
                "match_type": "INFERRED_PO_CANDIDATE",
                "matched_po_number": best_candidate["po_number"],
                "match_score": best_candidate["overall_score"],
                "po_record": matched_po,
                "amount_context": amount_context,
                "explanation": [
                    "Invoice does not contain a reliable PO reference.",
                    f"Best inferred PO candidate is {best_candidate['po_number']} with score {best_candidate['overall_score']}%.",
                    f"Vendor similarity score: {best_candidate['vendor_score']}%.",
                    f"Amount fit score: {best_candidate['amount_score']}%.",
                    f"Description similarity score: {best_candidate['description_score']}%.",
                    "Because PO was inferred instead of explicitly provided, this should go to human review rather than automatic approval."
                ]
            })

            return result

    result["explanation"] = [
        "No exact PO match found.",
        "No inferred PO candidate crossed the confidence threshold.",
        "Invoice should be routed to AP review."
    ]

    return result