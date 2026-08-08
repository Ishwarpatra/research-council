# Research Consensus Council - Agents & Skills Documentation

This document details the custom agents, core persona agents, and custom skills implemented in the **Research Consensus Council** repository, satisfying **Submission Checkpoint #4**.

---

## 1. Custom Agent: Prior Art Validator

* **Implementation File:** [`skills/prior_art_validator.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/prior_art_validator.py) & [`skills/audit/prior_art.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/audit/prior_art.py)
* **Registered Tool Schema:** `query_prior_art` in [`skills/agent_tools.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/agent_tools.py)
* **System Role:** Cross-references literature claims made during deliberation against local vector databases (ChromaDB) and verified academic publications.

### Execution & Trigger Mechanism
* **Automated Round 2 Trigger:** Automatically invoked during Round 2 of the deliberation engine state loop whenever interim consensus drops below `3.5` or when high disagreement is detected among primary reviewer agents.
* **Explicit Agent Invocation:** Primary deliberation agents can request verification using `dispatch_tool("query_prior_art", {"query": "..."})`.
* **Hybrid Search Mode:** Utilizes ChromaDB vector embeddings for fast local similarity retrieval, and optionally calls Jina AI reranking/embedding endpoints when `JINA_API_KEY` is configured.

---

## 2. Core Deliberation Agents

| Agent Name | Persona Model | Criterion | Weight | Primary Responsibilities |
| --- | --- | --- | --- | --- |
| **Skeptical Reviewer** | Orca-2 | Clarity & Presentation | 20% | Critical evaluator hunting for logical fallacies, overstatements, and formatting ambiguities. |
| **Method Evaluator** | Phi-4 | Methodology Rigor | 25% | Detail-obsessed methodology specialist checking experimental design, statistical validity, and sample size. |
| **Domain Expert** | Mistral-7B | Novelty & Significance | 20% | Field authority comparing claims against prior art and checking academic impact. |
| **Ethics Officer** | Llama-3.2 | Ethics & Integrity | 20% | Safety safeguard evaluating IRB compliance, data privacy, dual-use risks, and fabrication red flags. |
| **Industry Translator** | Phi-3 | Practical Impact | 15% | Pragmatic implementation specialist assessing real-world feasibility, cost, and scalability. |

---

## 3. Custom Skills System

The repository exposes modular, pluggable custom skills located in the [`skills/`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/) directory.

### Skill 1: Semantic Vector Retrieval & Hybrid RAG
* **Implementation:** [`skills/retrieval/embed_store.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/retrieval/embed_store.py), [`skills/retrieval/jina_client.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/retrieval/rerank.py)
* **Capabilities:** 
  - Parses uploaded PDF/text papers into structured sections (Abstract, Methods, Results, Claims).
  - Embeds chunked text into ChromaDB collections.
  - Performs hybrid similarity search with optional BM25/rerank step.

### Skill 2: Jenni-Style Claim Grounding Verification
* **Implementation:** [`skills/review/claim_grounding.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/review/claim_grounding.py)
* **Registered Tool Schema:** `query_claim_grounding` in [`skills/agent_tools.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/agent_tools.py)
* **Capabilities:** Evaluates specific paper claims against extracted evidence spans in the Methods and Results sections, scoring confidence and flagging ungrounded claims.

### Skill 3: Consensus Engine Scoring Matrix
* **Implementation:** [`skills/base.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/base.py) & [`council.py`](file:///c:/Users/DELL/Desktop/codego/research-council/council.py)
* **Capabilities:** Deterministically combines agent scores generated in Round 3 according to criterion weights (20%, 25%, 20%, 20%, 15%), producing rounded scores and map-to-decision bands (Accept, Minor Revisions, Major Revisions, Reject).

### Skill 4: Quality & Bias Drift Auditor
* **Implementation:** [`skills/audit/bias_drift.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/audit/bias_drift.py) & [`skills/audit/score_consistency.py`](file:///c:/Users/DELL/Desktop/codego/research-council/skills/audit/score_consistency.py)
* **Capabilities:** Analyzes historical agent score drift (mean, min, max, count) across past deliberations stored in SQLite database (`council.db`), detecting systemic evaluation bias or agent hallucination.
