# AI Invoice Decision Copilot

AI Invoice Decision Copilot is a Streamlit-based workflow for Accounts Payable invoice processing.

It accepts a real vendor invoice PDF, extracts invoice fields, matches the invoice against a purchase order database, runs AP validation checks, and produces an auditable decision.

## Problem Statement

This project is built for PS-1: Invoice Processing — from PDF to decision.

A company receives vendor invoices as PDFs. The AP team manually checks each invoice against purchase orders, vendor status, duplicate history, and amount tolerance. This project automates that workflow end-to-end.

## Core Workflow

1. Upload invoice PDF
2. Extract PDF text
3. Parse invoice fields
4. Match invoice to purchase order
5. Validate vendor status
6. Check duplicate invoices
7. Check PO amount tolerance
8. Handle split PO / partial invoice cases
9. Generate final AP decision
10. Save run to dashboard history
11. Download audit JSON

## Key Features

- Real PDF input
- Live run view
- Invoice field extraction
- PO matching
- Fuzzy PO inference when PO number is missing
- Duplicate invoice detection
- Vendor approval validation
- Amount tolerance check
- Split PO / partial invoice handling
- Final decision output
- Audit checks table
- Dashboard with run history
- Inspectable past runs
- Downloadable audit JSON
- Optional Gemini AI business explanation

## Decisions Produced

- APPROVED
- APPROVED_PARTIAL_PO_INVOICE
- NEEDS_REVIEW_PO_INFERRED
- NEEDS_REVIEW_AMOUNT_VARIANCE
- NEEDS_REVIEW_NO_PO_MATCH
- NEEDS_REVIEW_MISSING_FIELDS
- NEEDS_REVIEW_VENDOR_MISMATCH
- REJECTED_DUPLICATE
- REJECTED_VENDOR_BLOCKED

## Edge Cases Implemented

### 1. Missing PO but inferable

The invoice does not include a PO number, but the vendor, amount, and description strongly match an existing PO.

Expected decision:

NEEDS_REVIEW_PO_INFERRED

Why: The system can suggest a likely PO, but it should not auto-approve because the PO was inferred.

### 2. Split PO / partial invoice

A PO has already been partially invoiced. The new invoice is checked against the remaining allowed PO balance.

Expected decision:

APPROVED_PARTIAL_PO_INVOICE

Why: The invoice is valid because the cumulative invoiced amount remains within PO tolerance.

### 3. Duplicate invoice

The invoice number and vendor already exist in processed invoice history.

Expected decision:

REJECTED_DUPLICATE

Why: Paying again would create duplicate payment risk.

### 4. Amount above tolerance

The invoice references a valid PO and approved vendor, but the amount exceeds allowed tolerance.

Expected decision:

NEEDS_REVIEW_AMOUNT_VARIANCE

Why: The invoice may include unapproved charges or require PO amendment.

## Demo Invoice Order

Use these files from `sample_invoices/`:

1. `happy_path_clean_invoice.pdf`
2. `edge_1_missing_po_infer_candidate.pdf`
3. `edge_2_split_po_partial_invoice.pdf`
4. `edge_3_duplicate_invoice.pdf`
5. `edge_4_amount_over_tolerance.pdf`

## Tech Stack

- Python
- Streamlit
- Pandas
- PyMuPDF
- RapidFuzz
- SQLite
