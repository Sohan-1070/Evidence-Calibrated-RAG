import streamlit as st
import subprocess
import sys
import re
from pathlib import Path


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="ECRAG",
    page_icon="📚",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("📚 Evidence-Calibrated RAG")

st.markdown(
    """
    **Evidence-aware question answering with verification,
    confidence estimation, and abstention.**
    """
)

st.divider()


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("ECRAG System")

    st.markdown(
        """
        ### Pipeline

        📄 Document  
        ↓  
        🔎 Retrieval  
        ↓  
        🤖 LLM Generation  
        ↓  
        🧩 Claim Decomposition  
        ↓  
        ✅ Evidence Verification  
        ↓  
        📊 Confidence Calibration  
        ↓  
        🎯 Final Decision
        """
    )

    st.divider()

    st.info(
        "The system answers only when sufficient evidence "
        "is available. Otherwise it can abstain."
    )


# ============================================================
# QUESTION INPUT
# ============================================================

st.subheader("Ask a question about the document")

question = st.text_area(
    "Enter your question:",
    placeholder="Example: What does the council use standard forms for?",
    height=100
)


# ============================================================
# RUN ECRAG
# ============================================================

if st.button(
    "🚀 Generate Answer",
    type="primary",
    use_container_width=True
):

    if not question.strip():

        st.warning("Please enter a question first.")

    else:

        with st.spinner(
            "Running ECRAG... This may take a little while on CPU."
        ):

            try:

                # ------------------------------------------------
                # RUN EXISTING BACKEND
                # ------------------------------------------------

                project_root = Path(__file__).resolve().parent

                backend_file = (
                    project_root
                    / "backend"
                    / "main.py"
                )


                process = subprocess.run(

                    [
                        sys.executable,
                        str(backend_file)
                    ],

                    input=question + "\nexit\n",

                    text=True,

                    capture_output=True,

                    cwd=str(project_root),

                    timeout=300
                )


                output = process.stdout

                error_output = process.stderr


                # ------------------------------------------------
                # HANDLE ERRORS
                # ------------------------------------------------

                if process.returncode != 0:

                    st.error(
                        "ECRAG encountered an error."
                    )

                    with st.expander(
                        "Technical error details"
                    ):

                        st.code(
                            error_output
                        )

                else:

                    # ====================================================
                    # EXTRACT FINAL DECISION
                    # ====================================================

                    decision_match = re.search(

                        r"FINAL DECISION:\s*(.+)",

                        output,

                        re.IGNORECASE
                    )


                    confidence_match = re.search(

                        r"CONFIDENCE:\s*([0-9.]+)",

                        output,

                        re.IGNORECASE
                    )


                    supported_match = re.search(

                        r"Supported:\s*(\d+)",

                        output,

                        re.IGNORECASE
                    )


                    contradicted_match = re.search(

                        r"Contradicted:\s*(\d+)",

                        output,

                        re.IGNORECASE
                    )


                    uncertain_match = re.search(

                        r"Uncertain:\s*(\d+)",

                        output,

                        re.IGNORECASE
                    )


                    # ====================================================
                    # EXTRACT ANSWER
                    # ====================================================

                    answer = ""

                    answer_match = re.search(

                        r"ANSWER\s*\n[-]+\s*\n(.*?)(?=\n={5,}|\Z)",

                        output,

                        re.DOTALL
                    )


                    if answer_match:

                        answer = (
                            answer_match
                            .group(1)
                            .strip()
                        )


                    # ====================================================
                    # VALUES
                    # ====================================================

                    decision = (

                        decision_match
                        .group(1)
                        .strip()
                        .upper()

                        if decision_match

                        else "UNKNOWN"
                    )


                    confidence = (

                        float(
                            confidence_match.group(1)
                        )

                        if confidence_match

                        else 0.0
                    )


                    supported = (

                        int(
                            supported_match.group(1)
                        )

                        if supported_match

                        else 0
                    )


                    contradicted = (

                        int(
                            contradicted_match.group(1)
                        )

                        if contradicted_match

                        else 0
                    )


                    uncertain = (

                        int(
                            uncertain_match.group(1)
                        )

                        if uncertain_match

                        else 0
                    )


                    # ====================================================
                    # DECISION DISPLAY
                    # ====================================================

                    st.divider()

                    st.subheader("🎯 Final Decision")


                    if decision == "ANSWER":

                        st.success(
                            f"🟢 ANSWER — Confidence: "
                            f"{confidence:.1%}"
                        )


                    elif decision == "ABSTAIN":

                        st.error(
                            f"🔴 ABSTAIN — Confidence: "
                            f"{confidence:.1%}"
                        )


                    elif decision == "WARN":

                        st.warning(
                            f"🟡 WARN — Confidence: "
                            f"{confidence:.1%}"
                        )


                    else:

                        st.info(
                            f"Decision: {decision}"
                        )


                    # ====================================================
                    # CONFIDENCE BAR
                    # ====================================================

                    st.write(
                        f"**Confidence: {confidence:.3f}**"
                    )

                    st.progress(
                        min(
                            max(confidence, 0.0),
                            1.0
                        )
                    )


                    # ====================================================
                    # ANSWER
                    # ====================================================

                    st.divider()

                    st.subheader("💬 Answer")


                    if answer:

                        st.write(answer)

                    else:

                        st.info(
                            "The system did not generate "
                            "a conventional answer."
                        )


                    # ====================================================
                    # VERIFICATION SUMMARY
                    # ====================================================

                    st.divider()

                    st.subheader(
                        "🔍 Claim Verification"
                    )


                    col1, col2, col3 = st.columns(3)


                    with col1:

                        st.metric(
                            "Supported",
                            supported
                        )


                    with col2:

                        st.metric(
                            "Contradicted",
                            contradicted
                        )


                    with col3:

                        st.metric(
                            "Uncertain",
                            uncertain
                        )


                    # ====================================================
                    # RAW ECRAG OUTPUT
                    # ====================================================

                    st.divider()

                    with st.expander(
                        "📋 View complete ECRAG pipeline output"
                    ):

                        st.code(
                            output,
                            language="text"
                        )


            except subprocess.TimeoutExpired:

                st.error(
                    "The ECRAG process took too long to finish."
                )


            except Exception as e:

                st.error(
                    f"Unexpected error: {e}"
                )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "ECRAG — Evidence-Calibrated Retrieval-Augmented Generation"
)