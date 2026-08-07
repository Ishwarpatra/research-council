# Research Consensus Council Agent Profiles & Skills

This document specifies the configurations, prompts, system roles, and skill boundaries of the agents constituting the Research Consensus Council.

## Agent Definitions

### 1. Skeptical Reviewer
- **Persona Model:** Orca-2
- **Assigned Criterion:** Clarity & Presentation (Weight: 20%)
- **System Role:** Critical evaluator hunting for logical fallacies, overstatements, ambiguities.
- **Responsibilities:** Question claims, identify weaknesses in formatting or logic, challenge peer ratings.

### 2. Method Evaluator
- **Persona Model:** Phi-4
- **Assigned Criterion:** Methodology Rigor (Weight: 25%)
- **System Role:** Detail-obsessed methodology specialist checking soundness.
- **Responsibilities:** Scrutinise experimental design, statistical validity, sample sizes, hidden confounds.

### 3. Domain Expert
- **Persona Model:** Mistral-7B
- **Assigned Criterion:** Novelty & Significance (Weight: 20%)
- **System Role:** Field knowledge authority validating originality.
- **Responsibilities:** Compare with prior art, check literature gaps, identify missing citations, evaluate academic impact.

### 4. Ethics Officer
- **Persona Model:** Llama-3.2
- **Assigned Criterion:** Ethics & Integrity (Weight: 20%)
- **System Role:** Safeguard of research, human, and animal safety standards.
- **Responsibilities:** Evaluate IRB compliance, privacy concerns, potential dual-use risks, and data fabrication warning signs.

### 5. Industry Translator
- **Persona Model:** Phi-3
- **Assigned Criterion:** Practical Impact (Weight: 15%)
- **System Role:** Pragmatic, deployment-focused, implementation specialist.
- **Responsibilities:** Assess real-world feasibility, implementation costs, scalability, commercial viability.

## System Prompt Blueprint
The base instructions are hosted in `council.py` as `BASE_PROMPT` and populated dynamically per round. Prompt injection defenses are applied (capping justifications and sanitizing peer review strings) to guarantee reliability and protect context windows.

## Skills and Engine Tools

### 1. Ingestion / PDF Extraction Module (`pdfplumber` / `pypdf`)
- **Capability:** Parses PDF/Text documents, automatically separating the flow into structured chunks: Abstract, Methods, Results, and Claims.
- **Table Extraction:** Normalizes tabular cells by calculating column widths, padding values with spaces, and outputting clean formatted text tables.
- **Citation Extraction:** Uses regular expressions to extract citations (`[1]`, `(Author, Year)`) from the text blocks without length constraints.

### 2. Consensus Engine Scoring Matrix (`ScoreCalculator`)
- **Capability:** Deterministically combines scores generated in Round 3 by each agent according to their respective criterion weight. Computes rounded scores (2 decimal places) to match decision bands.

### 3. Quality & Bias Auditor (`run_monthly_audit`)
- **Capability:** Tallies the drift (mean, min, max, count) of each agent's Round 3 scores across all deliberations in the database. Compares outcomes with human benchmarks.

### 4. Interactive Human-in-the-Loop Processor
- **Capability:** Pauses execution at round boundaries to enable reviews of intermediate prompts, justifications, and scores. Allows developers/evaluators to approve, override, or abort execution.

## Custom Agent: Prior Art Validator
- **Role**: Cross-references claims made by the primary deliberation agents against a local dataset of verified research papers.
- **Trigger Mechanism**: Invoked during Round 2 of the deliberation state engine if the consensus score drops below a 3.5 threshold, or if an agent explicitly requests claim verification.

## Custom Skill: Semantic Vector Retrieval (ChromaDB)
- **Description**: A local retrieval-augmented generation (RAG) tool that performs semantic searches against an offline ChromaDB instance to retrieve relevant source documents without incurring external API latency.

### LLM Tool Integration Schema (OpenAI Format)
The following JSON schema is injected into the payload when routing to the Prior Art Validator agent:

```json
{
  "type": "function",
  "function": {
    "name": "query_prior_art",
    "description": "Searches the local vector database for existing research and prior art related to a specific scientific claim.",
    "parameters": {
      "type": "object",
      "properties": {
        "query_text": {
          "type": "string",
          "description": "The specific scientific claim or keyword phrase to verify against the local database."
        },
        "n_results": {
          "type": "integer",
          "description": "The number of top semantic matches to retrieve. Defaults to 3.",
          "minimum": 1,
          "maximum": 5
        }
      },
      "required": ["query_text"],
      "additionalProperties": false
    }
  }
}
```
