# ECRAG: Evidence-Calibrated Retrieval-Augmented Generation

[![Streamlit](https://img.shields.io/badge/Streamlit-1.64-FF4B4B.svg)](https://streamlit.io)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Verification Pipeline](https://img.shields.io/badge/Pipeline-7--Stage%20Verification-purple.svg)]()

> **ECRAG** is an advanced AI factual verification and question-answering system designed to eliminate hallucination in Retrieval-Augmented Generation through a multi-tier search engine, confidence calibration, and an integrated **7-Stage Factual Verification Pipeline**.

---

## 🌟 Key Highlights

* **🔬 7-Stage Factual Verification Pipeline**:
  1. **Official Sources**: Government (`.gov`), WHO, and institutional documentation.
  2. **Primary Evidence**: Research datasets, official reports, direct whitepapers.
  3. **Reference Sources**: Wikipedia, encyclopedic authorities, curated knowledge.
  4. **Academic Sources**: Peer-reviewed literature, university repositories.
  5. **Reputable News**: Tier-1 international and national news coverage (Google News RSS).
  6. **Community Sources**: Web discussions, blogs, and grassroots leads (treated as leads only, never conclusive proof).
  7. **Final Validation**: Claim-by-claim verification ledger (`VERIFIED`, `PARTIALLY_VERIFIED`, `CONTRADICTED`, `UNVERIFIED`) with confidence scoring.

* **🌐 3 Execution Modes**:
  * **Online Mode**: Powered by Google Gemini 3.6 Flash and multi-tier live search.
  * **Offline / Island Mode**: Completely air-gapped using local ChromaDB vector stores and local models.
  * **Document Mode**: Upload any reference PDF to query, analyze, and cite document pages directly.

* **💬 Multi-Session Chat Segments**:
  * Persistent SQLite chat history segmented by sessions.
  * Search, review, switch, and delete past conversations.

* **🛡️ Zero Hallucination Guardrails**:
  * When insufficient evidence is available, the system abstains rather than inventing answers.

---

## 🚀 Quick Start (Local Setup)

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/ECRAG.git
cd ECRAG
```

### 2. Set Up Virtual Environment
```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure API Keys
Create a `.env` file or export your Gemini API key:
```bash
export GEMINI_API_KEY="your_gemini_api_key_here"
```

### 5. Launch the Application
```bash
streamlit run app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## ☁️ 1-Click Free Cloud Deployment (Streamlit Cloud)

You can host ECRAG completely free on **Streamlit Community Cloud** with a permanent public URL:

1. Push this repository to your GitHub account (instructions below).
2. Go to **[share.streamlit.io](https://share.streamlit.io)** and log in with GitHub.
3. Click **"New app"**.
4. Select your repository: `YOUR_USERNAME/ECRAG`, Branch: `main`, Main file path: `app.py`.
5. Under **"Advanced settings" -> "Secrets"**, add your API key:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   ECRAG_GEMINI_MODEL = "gemini-3.6-flash"
   ECRAG_OFFLINE = "0"
   ```
6. Click **Deploy!** Your app will be live 24/7 with a shareable public URL (e.g. `https://ecrag-verification.streamlit.app`).

---

## 🧪 Running Unit Tests

The test suite covers the 7-stage verification ledger, source ranking, live retrieval, and evidence formatting:
```bash
python -m unittest discover tests
```

---

## 📂 Project Structure

```text
├── app.py                      # Main Streamlit web application & interface
├── requirements.txt            # Python dependencies
├── README.md                   # Project documentation
├── .gitignore                  # Git exclusion rules
├── .env.example                # Sample environment file
├── backend/                    # Core verification & RAG engine
│   ├── engine.py               # Local RAG engine & confidence scoring
│   ├── main.py                 # CLI entry point
│   ├── verification/           # 7-stage verification pipeline
│   │   ├── pipeline.py         # Multi-stage orchestrator & SSE streaming
│   │   ├── claim_ledger.py     # Claim ledger & verdict evaluation
│   │   ├── sources.py          # Multi-tier evidence retrieval & ranking
│   │   └── verifier.py         # Claim verification logic
│   └── calibration/            # Confidence calibration algorithms
├── data/                       # Offline knowledge base documents & reference guides
└── tests/                      # Verification pipeline unit tests
```

---

## 📜 License
MIT License. Free to use, modify, and distribute for academic and commercial purposes.

