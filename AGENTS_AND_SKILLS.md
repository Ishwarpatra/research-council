# Agents and Skills Specifications

This document catalogs the custom agent implementations and tool boundaries in the Research Consensus Council.

## Council Agents
- **Skeptical Reviewer** (Orca-2): Focuses on *Clarity & Presentation* (Weight = 0.20)
- **Method Evaluator** (Phi-4): Focuses on *Methodology Rigor* (Weight = 0.25)
- **Domain Expert** (Mistral-7B): Focuses on *Novelty & Significance* (Weight = 0.20)
- **Ethics Officer** (Llama-3.2): Focuses on *Ethics & Integrity* (Weight = 0.20)
- **Industry Translator** (Phi-3): Focuses on *Practical Impact* (Weight = 0.15)

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
* **Role**: Cross-references claims made by the primary deliberation agents against a local dataset of verified research papers.
* **Trigger Mechanism**: Invoked during Round 2 of the deliberation state engine if the consensus score drops below a 3.5 threshold, or if an agent explicitly requests claim verification.

## Custom Skill: Semantic Vector Retrieval (ChromaDB)
* **Description**: A local retrieval-augmented generation (RAG) tool that performs semantic searches against an offline ChromaDB instance to retrieve relevant source documents without incurring external API latency.

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
