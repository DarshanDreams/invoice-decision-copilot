from typing import Dict, Any
import pandas as pd
from rapidfuzz import fuzz


def normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def check_duplicate_invoice(
    parsed_invoice: Dict[str, Any],
    processed_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Check whether the invoice has already been processed.
    Duplicate detection uses invoice number + vendor name.
    """

    invoice_number = normalize(parsed_invoice.get("invoice_number"))
    vendor_name = normalize(parsed_invoice.get("vendor_name"))

    if not invoice_number:
        return {
            "is_duplicate": False,
            "matched_record": None,
            "reason": "Invoice number is missing, so duplicate check is limited."
        }

    for _, row in processed_df.iterrows():
        existing_invoice_number = normalize(row.get("invoice_number"))
        existing_vendor = normalize(row.get("vendor_name"))

        invoice_number_matches = invoice_number == existing_invoice_number
        vendor_matches = vendor_name == existing_vendor

        if invoice_number_matches and vendor_matches:
            return {
                "is_duplicate": True,
                "matched_record": row.to_dict(),
                "reason": (
                    f"Invoice number {parsed_invoice.get('invoice_number')} "
                    f"from vendor {parsed_invoice.get('vendor_name')} "
                    "already exists in processed invoice history."
                )
            }

    return {
        "is_duplicate": False,
        "matched_record": None,
        "reason": "No duplicate invoice found in processed history."
    }


def check_vendor_consistency(
    parsed_invoice: Dict[str, Any],
    po_record: Dict[str, Any] | None
) -> Dict[str, Any]:
    """
    Check if vendor name on invoice is consistent with vendor name on matched PO.
    """

    if not po_record:
        return {
            "is_consistent": False,
            "score": 0,
            "reason": "No PO record available for vendor consistency check."
        }

    invoice_vendor = normalize(parsed_invoice.get("vendor_name"))
    po_vendor = normalize(po_record.get("vendor_name"))

    score = fuzz.token_sort_ratio(invoice_vendor, po_vendor)

    return {
        "is_consistent": score >= 85,
        "score": round(score, 2),
        "reason": (
            f"Invoice vendor '{parsed_invoice.get('vendor_name')}' "
            f"compared with PO vendor '{po_record.get('vendor_name')}'. "
            f"Similarity score: {round(score, 2)}%."
        )
    }


def build_audit_check(
    check_name: str,
    status: str,
    detail: str
) -> Dict[str, str]:
    return {
        "check": check_name,
        "status": status,
        "detail": detail
    }


def make_decision(
    parsed_invoice: Dict[str, Any],
    po_match_result: Dict[str, Any],
    processed_df: pd.DataFrame
) -> Dict[str, Any]:
    """
    Final business decision engine.

    Priority order matters:
    1. Missing critical fields
    2. Duplicate detection
    3. PO match availability
    4. Vendor approval/status
    5. Vendor consistency
    6. PO inference review
    7. Amount tolerance/balance
    8. Partial PO handling
    9. Approval
    """

    audit_checks = []
    reasons = []
    recommended_actions = []

    po_record = po_match_result.get("po_record")
    amount_context = po_match_result.get("amount_context")

    # 1. Missing critical fields
    missing_fields = parsed_invoice.get("missing_fields", [])

    if missing_fields:
        audit_checks.append(
            build_audit_check(
                "Critical field completeness",
                "FAILED",
                "Missing fields: " + ", ".join(missing_fields)
            )
        )

        return {
            "decision": "NEEDS_REVIEW_MISSING_FIELDS",
            "decision_category": "NEEDS_REVIEW",
            "risk_level": "HIGH",
            "summary": "Invoice is missing critical fields required for automated AP approval.",
            "reasons": [
                "The invoice could not be processed automatically because critical fields are missing.",
                "Missing fields: " + ", ".join(missing_fields)
            ],
            "recommended_actions": [
                "Ask vendor to resend invoice with missing details.",
                "AP reviewer should manually verify the invoice before any payment action."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "Critical field completeness",
            "PASSED",
            "Invoice number, invoice date, vendor name, and total amount were extracted."
        )
    )

    # 2. Duplicate detection
    duplicate_result = check_duplicate_invoice(parsed_invoice, processed_df)

    if duplicate_result["is_duplicate"]:
        audit_checks.append(
            build_audit_check(
                "Duplicate invoice check",
                "FAILED",
                duplicate_result["reason"]
            )
        )

        return {
            "decision": "REJECTED_DUPLICATE",
            "decision_category": "REJECTED",
            "risk_level": "HIGH",
            "summary": "Invoice was rejected because it appears to be a duplicate.",
            "reasons": [
                duplicate_result["reason"],
                "Paying this invoice again could create duplicate payment risk."
            ],
            "recommended_actions": [
                "Do not process payment.",
                "Review the previously processed invoice record.",
                "Contact vendor only if they claim this is a corrected or replacement invoice."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "Duplicate invoice check",
            "PASSED",
            duplicate_result["reason"]
        )
    )

    # 3. PO match availability
    if not po_match_result.get("po_found"):
        audit_checks.append(
            build_audit_check(
                "PO matching",
                "FAILED",
                "No exact or reliable inferred PO match was found."
            )
        )

        return {
            "decision": "NEEDS_REVIEW_NO_PO_MATCH",
            "decision_category": "NEEDS_REVIEW",
            "risk_level": "HIGH",
            "summary": "Invoice requires manual review because no reliable PO match was found.",
            "reasons": [
                "The invoice could not be linked to a known purchase order.",
                "Without a PO match, the system cannot validate approved amount, vendor, or remaining PO balance."
            ],
            "recommended_actions": [
                "Ask vendor to provide the correct PO number.",
                "AP reviewer should search procurement records manually.",
                "Do not approve automatically."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "PO matching",
            "PASSED",
            f"Matched PO: {po_match_result.get('matched_po_number')} using {po_match_result.get('match_type')}."
        )
    )

    # 4. Vendor approval/status
    vendor_status = str(po_record.get("vendor_status", "")).upper()

    if vendor_status == "BLOCKED":
        audit_checks.append(
            build_audit_check(
                "Vendor approval status",
                "FAILED",
                f"Vendor status is {vendor_status}."
            )
        )

        return {
            "decision": "REJECTED_VENDOR_BLOCKED",
            "decision_category": "REJECTED",
            "risk_level": "HIGH",
            "summary": "Invoice was rejected because the matched vendor is blocked.",
            "reasons": [
                f"Vendor '{po_record.get('vendor_name')}' is marked as BLOCKED in the PO database.",
                "Blocked vendors should not be paid without procurement/compliance override."
            ],
            "recommended_actions": [
                "Do not process payment.",
                "Escalate to procurement or compliance.",
                "Ask for vendor re-verification if needed."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "Vendor approval status",
            "PASSED",
            f"Vendor status is {vendor_status}."
        )
    )

    # 5. Vendor consistency
    vendor_consistency = check_vendor_consistency(parsed_invoice, po_record)

    if not vendor_consistency["is_consistent"]:
        audit_checks.append(
            build_audit_check(
                "Vendor consistency",
                "FAILED",
                vendor_consistency["reason"]
            )
        )

        return {
            "decision": "NEEDS_REVIEW_VENDOR_MISMATCH",
            "decision_category": "NEEDS_REVIEW",
            "risk_level": "MEDIUM",
            "summary": "Invoice requires review because invoice vendor does not closely match PO vendor.",
            "reasons": [
                vendor_consistency["reason"],
                "The PO number may be correct, but the vendor identity is not consistent enough for automatic approval."
            ],
            "recommended_actions": [
                "AP reviewer should verify whether the vendor name difference is legitimate.",
                "Check vendor master data and PO ownership.",
                "Do not auto-approve."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "Vendor consistency",
            "PASSED",
            vendor_consistency["reason"]
        )
    )

    # 6. PO was inferred, not explicitly provided
    if po_match_result.get("match_type") == "INFERRED_PO_CANDIDATE":
        audit_checks.append(
            build_audit_check(
                "PO reference quality",
                "REVIEW",
                "PO was inferred using vendor, amount, and description rather than explicitly present on invoice."
            )
        )

        return {
            "decision": "NEEDS_REVIEW_PO_INFERRED",
            "decision_category": "NEEDS_REVIEW",
            "risk_level": "MEDIUM",
            "summary": "Likely PO found, but invoice requires review because PO number was missing.",
            "reasons": [
                f"Best inferred PO candidate is {po_match_result.get('matched_po_number')} with score {po_match_result.get('match_score')}%.",
                "The system can suggest a likely PO, but should not auto-approve when the vendor did not provide a PO reference."
            ],
            "recommended_actions": [
                "AP reviewer should confirm the suggested PO.",
                "Ask vendor to include PO number on future invoices.",
                "Approve only after human confirmation."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "PO reference quality",
            "PASSED",
            "Invoice explicitly referenced a valid PO."
        )
    )

    # 7. Amount tolerance / remaining balance
    if not amount_context.get("amount_within_remaining_balance"):
        invoice_total = amount_context.get("invoice_total")
        remaining_allowed = amount_context.get("remaining_allowed_amount")

        audit_checks.append(
            build_audit_check(
                "Amount tolerance and remaining PO balance",
                "FAILED",
                (
                    f"Invoice total is {invoice_total:,.2f}, "
                    f"but remaining allowed PO balance is {remaining_allowed:,.2f}."
                )
            )
        )

        return {
            "decision": "NEEDS_REVIEW_AMOUNT_VARIANCE",
            "decision_category": "NEEDS_REVIEW",
            "risk_level": "MEDIUM",
            "summary": "Invoice amount exceeds the remaining PO balance including tolerance.",
            "reasons": [
                f"Invoice total is {po_record.get('currency')} {invoice_total:,.2f}.",
                f"Remaining allowed PO balance is {po_record.get('currency')} {remaining_allowed:,.2f}.",
                "The invoice may include unapproved charges, delivery fees, tax differences, or incorrect billing."
            ],
            "recommended_actions": [
                "AP reviewer should verify the variance.",
                "Ask procurement whether PO should be amended.",
                "Do not auto-approve until variance is resolved."
            ],
            "audit_checks": audit_checks
        }

    audit_checks.append(
        build_audit_check(
            "Amount tolerance and remaining PO balance",
            "PASSED",
            "Invoice amount is within remaining PO balance including tolerance."
        )
    )

    # 8. Split PO / partial invoice
    already_invoiced = float(amount_context.get("already_invoiced_amount", 0))

    if already_invoiced > 0:
        return {
            "decision": "APPROVED_PARTIAL_PO_INVOICE",
            "decision_category": "APPROVED",
            "risk_level": "LOW",
            "summary": "Invoice approved as a valid partial invoice against an existing PO.",
            "reasons": [
                f"PO {po_match_result.get('matched_po_number')} has already invoiced amount of {po_record.get('currency')} {already_invoiced:,.2f}.",
                f"This invoice total is within remaining allowed balance of {po_record.get('currency')} {amount_context.get('remaining_allowed_amount'):,.2f}.",
                "This looks like a valid split or partial PO invoice."
            ],
            "recommended_actions": [
                "Approve for payment.",
                "Update processed invoice history after payment approval.",
                "Continue monitoring cumulative invoices against this PO."
            ],
            "audit_checks": audit_checks
        }

    # 9. Clean approval
    return {
        "decision": "APPROVED",
        "decision_category": "APPROVED",
        "risk_level": "LOW",
        "summary": "Invoice approved. It passed PO, vendor, duplicate, and amount validation checks.",
        "reasons": [
            "Invoice contains all critical fields.",
            "No duplicate invoice was found.",
            f"Invoice explicitly matches PO {po_match_result.get('matched_po_number')}.",
            "Vendor is approved.",
            "Invoice amount is within PO tolerance and remaining balance."
        ],
        "recommended_actions": [
            "Approve for payment.",
            "Store invoice decision in audit history.",
            "Update processed invoice record after payment approval."
        ],
        "audit_checks": audit_checks
    }