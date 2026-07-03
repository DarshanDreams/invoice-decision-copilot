import json
import streamlit as st
import pandas as pd

from utils.pdf_extractor import extract_text_from_pdf
from utils.invoice_parser import parse_invoice_text
from utils.po_matcher import match_invoice_to_po
from utils.decision_engine import make_decision
from utils.storage import save_run, load_run_history, load_full_run, clear_history


st.set_page_config(
    page_title="AI Invoice Decision Copilot",
    page_icon="🧾",
    layout="wide"
)


# -----------------------------
# Helper functions
# -----------------------------

def render_decision_badge(decision_result):
    category = decision_result["decision_category"]

    if category == "APPROVED":
        st.success(f'✅ {decision_result["decision"]}')
    elif category == "REJECTED":
        st.error(f'❌ {decision_result["decision"]}')
    else:
        st.warning(f'⚠️ {decision_result["decision"]}')


def safe_money(currency, amount):
    if amount is None:
        return "Missing"

    try:
        return f"{currency} {float(amount):,.2f}"
    except Exception:
        return str(amount)


def save_run_once(file_name, parsed_invoice, po_match_result, decision_result):
    """
    Prevent duplicate saves caused by Streamlit reruns.
    """

    signature = (
        file_name,
        parsed_invoice.get("invoice_number"),
        decision_result.get("decision")
    )

    if "last_saved_signature" not in st.session_state:
        st.session_state.last_saved_signature = None

    if st.session_state.last_saved_signature != signature:
        save_run(
            file_name,
            parsed_invoice,
            po_match_result,
            decision_result
        )
        st.session_state.last_saved_signature = signature
        return True

    return False

# -----------------------------
# Load data
# -----------------------------

po_df = pd.read_csv("data/purchase_orders.csv")
processed_df = pd.read_csv("data/processed_invoices.csv")


# -----------------------------
# App layout
# -----------------------------

st.title("🧾 AI Invoice Decision Copilot")
st.caption("Invoice PDF → PO Matching → Business Rules → AI Explanation → Decision → Audit Trail")

st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    ["Run Invoice Process", "Dashboard", "PO Database"]
)

st.sidebar.divider()

st.sidebar.markdown("### Demo Order")
st.sidebar.markdown(
    """
1. `happy_path_clean_invoice.pdf`  
2. `edge_1_missing_po_infer_candidate.pdf`  
3. `edge_2_split_po_partial_invoice.pdf`  
4. `edge_3_duplicate_invoice.pdf`  
5. `edge_4_amount_over_tolerance.pdf`
"""
)

st.sidebar.divider()

st.sidebar.markdown("### Process Stages")
st.sidebar.markdown(
    """
- PDF intake  
- Text extraction  
- Field parsing  
- PO matching  
- AP validation  
- Business explanation
- Final decision  
- Audit history  
"""
)


# -----------------------------
# Page 1: Run Invoice Process
# -----------------------------

if page == "Run Invoice Process":
    st.header("Run Invoice Process")

    st.markdown(
        """
This workflow accepts a real vendor invoice PDF, extracts structured invoice data,
matches it against purchase orders, runs AP validation checks, and produces an
auditable decision.
"""
    )

    uploaded_file = st.file_uploader(
        "Upload vendor invoice PDF",
        type=["pdf"]
    )

    if uploaded_file:
        st.success("Invoice uploaded successfully.")

        st.subheader("Live Run View")

        extraction_result = None
        parsed_invoice = None
        po_match_result = None
        decision_result = None

        with st.status("Running invoice process...", expanded=True) as status:

            st.write("✅ 1. Invoice PDF received")

            extraction_result = extract_text_from_pdf(uploaded_file)

            if extraction_result["success"]:
                st.write("✅ 2. PDF text extraction completed")

                if extraction_result["is_probably_scanned"]:
                    st.warning(
                        "This PDF looks scanned or image-based. "
                        "Text extraction is limited. OCR fallback can be added later."
                    )
                else:
                    st.write("✅ 3. PDF is machine-readable")

                parsed_invoice = parse_invoice_text(extraction_result["text"])

                st.write("✅ 4. Invoice fields parsed")

                if parsed_invoice["missing_fields"]:
                    st.warning(
                        "Some critical fields are missing: "
                        + ", ".join(parsed_invoice["missing_fields"])
                    )
                else:
                    st.write("✅ 5. Critical invoice fields found")

                po_match_result = match_invoice_to_po(parsed_invoice, po_df)

                if po_match_result["po_found"]:
                    if po_match_result["match_type"] == "EXACT_PO_MATCH":
                        st.write("✅ 6. Exact PO match found")
                    elif po_match_result["match_type"] == "INFERRED_PO_CANDIDATE":
                        st.write("⚠️ 6. PO missing, likely PO candidate inferred")
                    else:
                        st.write("⚠️ 6. PO match requires review")
                else:
                    st.write("❌ 6. No reliable PO match found")

                decision_result = make_decision(
                    parsed_invoice,
                    po_match_result,
                    processed_df
                )

                st.write("✅ 7. Business validation rules executed")
                st.write(f'✅ 8. Final decision generated: {decision_result["decision"]}')

                saved_now = save_run_once(
                    uploaded_file.name,
                    parsed_invoice,
                    po_match_result,
                    decision_result
                )

                if saved_now:
                    st.write("✅ 9. Run saved to dashboard history")
                else:
                    st.write("ℹ️ 9. Run already saved in this session")

                st.write("✅ 10. AI explanation layer ready")

                status.update(
                    label="Invoice process completed",
                    state="complete"
                )

            else:
                st.write("❌ 2. PDF extraction failed")
                st.error(extraction_result["error"])

                status.update(
                    label="PDF extraction failed",
                    state="error"
                )

        if extraction_result and extraction_result["success"]:

            # -----------------------------
            # Final Decision
            # -----------------------------

            st.subheader("Final Decision")
            render_decision_badge(decision_result)

            decision_col1, decision_col2, decision_col3 = st.columns(3)

            with decision_col1:
                st.metric("Risk Level", decision_result["risk_level"])

            with decision_col2:
                st.metric("Decision Category", decision_result["decision_category"])

            with decision_col3:
                st.metric(
                    "Invoice Total",
                    safe_money(
                        parsed_invoice.get("currency"),
                        parsed_invoice.get("total_amount")
                    )
                )

            st.info(decision_result["summary"])

            st.markdown("### Reasons")
            for reason in decision_result["reasons"]:
                st.write("- " + reason)

            st.markdown("### Recommended Actions")
            for action in decision_result["recommended_actions"]:
                st.write("- " + action)

            st.markdown("### Business Decision Explanation")

            business_explanation = (
            f'The invoice was classified as {decision_result["decision"]}. '
            f'{decision_result["summary"]} '
            'This decision was generated using transparent AP validation checks, including '
            'invoice field completeness, PO matching, duplicate detection, vendor validation, '
            'vendor consistency, and PO amount tolerance.')

            st.write(business_explanation)


            audit_payload = {
                "file_name": uploaded_file.name,
                "parsed_invoice": parsed_invoice,
                "po_match_result": po_match_result,
                "decision_result": decision_result,
                "business_explanation": business_explanation
            }

            st.download_button(
                label="Download Audit JSON",
                data=json.dumps(audit_payload, indent=2, default=str),
                file_name=f'audit_{parsed_invoice.get("invoice_number", "invoice")}.json',
                mime="application/json"
            )

            st.divider()

            # -----------------------------
            # Parsed Invoice Fields
            # -----------------------------

            st.subheader("Parsed Invoice Fields")

            parsed_col1, parsed_col2, parsed_col3 = st.columns(3)

            with parsed_col1:
                st.metric("Invoice Number", parsed_invoice["invoice_number"] or "Missing")
                st.metric("Vendor", parsed_invoice["vendor_name"] or "Missing")

            with parsed_col2:
                st.metric("Invoice Date", parsed_invoice["invoice_date"] or "Missing")
                st.metric("PO Number", parsed_invoice["po_number"] or "Missing")

            with parsed_col3:
                st.metric("Currency", parsed_invoice["currency"] or "Missing")
                st.metric("Parse Confidence", f'{parsed_invoice["parse_confidence"] * 100:.0f}%')

            st.metric(
                "Total Amount",
                safe_money(
                    parsed_invoice.get("currency"),
                    parsed_invoice.get("total_amount")
                )
            )

            st.divider()

            # -----------------------------
            # PO Matching Result
            # -----------------------------

            st.subheader("PO Matching Result")

            if po_match_result["po_found"]:
                match_col1, match_col2, match_col3 = st.columns(3)

                with match_col1:
                    st.metric("Match Type", po_match_result["match_type"])

                with match_col2:
                    st.metric("Matched PO", po_match_result["matched_po_number"])

                with match_col3:
                    st.metric("Match Score", f'{po_match_result["match_score"]:.0f}%')

                po_record = po_match_result["po_record"]
                amount_context = po_match_result["amount_context"]

                detail_col1, detail_col2, detail_col3, detail_col4 = st.columns(4)

                with detail_col1:
                    st.metric("PO Vendor", po_record.get("vendor_name"))

                with detail_col2:
                    st.metric("Vendor Status", po_record.get("vendor_status"))

                with detail_col3:
                    st.metric(
                        "PO Amount",
                        safe_money(
                            po_record.get("currency"),
                            amount_context["po_amount"]
                        )
                    )

                with detail_col4:
                    st.metric(
                        "Remaining Allowed",
                        safe_money(
                            po_record.get("currency"),
                            amount_context["remaining_allowed_amount"]
                        )
                    )

                if amount_context["amount_within_remaining_balance"]:
                    st.success("Invoice amount is within remaining PO balance including tolerance.")
                else:
                    st.warning("Invoice amount is above remaining PO balance including tolerance.")

            else:
                st.error("No reliable PO match found.")

            st.divider()

            # -----------------------------
            # Audit Checks
            # -----------------------------

            st.subheader("Audit Checks")

            audit_df = pd.DataFrame(decision_result["audit_checks"])
            st.dataframe(audit_df, use_container_width=True)

            # -----------------------------
            # Expanders
            # -----------------------------

            if po_match_result["candidate_pos"]:
                with st.expander("View top PO candidates"):
                    st.dataframe(
                        pd.DataFrame(po_match_result["candidate_pos"]),
                        use_container_width=True
                    )

            with st.expander("Why this PO match happened"):
                for line in po_match_result["explanation"]:
                    st.write("- " + line)

                if po_match_result["warnings"]:
                    st.warning("\n".join(po_match_result["warnings"]))

            with st.expander("View final decision JSON"):
                st.json(decision_result)

            with st.expander("View parsed invoice JSON"):
                st.json(parsed_invoice)

            with st.expander("View PO match JSON"):
                st.json(po_match_result)

            with st.expander("View raw extracted text"):
                st.text_area(
                    "Raw invoice text",
                    extraction_result["text"],
                    height=350
                )

    else:
        st.warning("Upload an invoice PDF to start the process.")


# -----------------------------
# Page 2: Dashboard
# -----------------------------

elif page == "Dashboard":
    st.header("Run History Dashboard")

    st.markdown(
        """
This dashboard shows invoice runs across time, including status, output decision,
risk level, and audit details.
"""
    )

    history_df = load_run_history()

    if history_df.empty:
        st.info("No invoice runs yet. Process an invoice first.")
    else:
        total_runs = len(history_df)
        approved_runs = len(history_df[history_df["decision_category"] == "APPROVED"])
        review_runs = len(history_df[history_df["decision_category"] == "NEEDS_REVIEW"])
        rejected_runs = len(history_df[history_df["decision_category"] == "REJECTED"])

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

        with metric_col1:
            st.metric("Total Runs", total_runs)

        with metric_col2:
            st.metric("Approved", approved_runs)

        with metric_col3:
            st.metric("Needs Review", review_runs)

        with metric_col4:
            st.metric("Rejected", rejected_runs)

        st.divider()

        st.subheader("Decision Breakdown")

        breakdown_df = (
            history_df["decision_category"]
            .value_counts()
            .reset_index()
        )

        breakdown_df.columns = ["Decision Category", "Count"]

        st.bar_chart(
            breakdown_df,
            x="Decision Category",
            y="Count"
        )

        st.divider()

        st.subheader("All Runs")

        st.dataframe(
            history_df,
            use_container_width=True
        )

        st.divider()

        st.subheader("Inspect One Run")

        selected_id = st.selectbox(
            "Select run ID",
            history_df["id"].tolist()
        )

        selected_run = load_full_run(selected_id)

        if selected_run:
            decision_json = selected_run["decision_json"]
            parsed_json = selected_run["parsed_invoice_json"]
            po_match_json = selected_run["po_match_json"]

            st.markdown("### Selected Run Summary")

            run_col1, run_col2, run_col3 = st.columns(3)

            with run_col1:
                st.metric("Decision", decision_json["decision"])

            with run_col2:
                st.metric("Risk Level", decision_json["risk_level"])

            with run_col3:
                st.metric("Category", decision_json["decision_category"])

            st.info(decision_json["summary"])

            st.markdown("### Reasons")
            for reason in decision_json["reasons"]:
                st.write("- " + reason)

            st.markdown("### Recommended Actions")
            for action in decision_json["recommended_actions"]:
                st.write("- " + action)

            st.markdown("### Audit Checks")
            st.dataframe(
                pd.DataFrame(decision_json["audit_checks"]),
                use_container_width=True
            )

            selected_payload = {
                "run_id": selected_id,
                "run_timestamp": selected_run["run_timestamp"],
                "file_name": selected_run["file_name"],
                "parsed_invoice": parsed_json,
                "po_match_result": po_match_json,
                "decision_result": decision_json
            }

            st.download_button(
                label="Download Selected Run Audit JSON",
                data=json.dumps(selected_payload, indent=2, default=str),
                file_name=f"run_{selected_id}_audit.json",
                mime="application/json"
            )

            with st.expander("Full decision JSON"):
                st.json(decision_json)

            with st.expander("Parsed invoice JSON"):
                st.json(parsed_json)

            with st.expander("PO match JSON"):
                st.json(po_match_json)

        st.divider()

        if st.button("Clear run history"):
            clear_history()
            st.success("Run history cleared. Refresh the page.")


# -----------------------------
# Page 3: PO Database
# -----------------------------

elif page == "PO Database":
    st.header("Purchase Order Database")

    st.markdown(
        """
This table acts as the mock procurement system used by the workflow for PO matching,
vendor validation, tolerance checks, and split PO handling.
"""
    )

    st.dataframe(
        po_df,
        use_container_width=True
    )

    st.divider()

    st.subheader("Processed Invoice Seed Data")

    st.markdown(
        """
This table is used for duplicate detection and existing invoice history checks.
"""
    )

    st.dataframe(
        processed_df,
        use_container_width=True
    )