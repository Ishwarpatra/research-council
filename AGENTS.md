# Research Consensus Council Agent Profiles

This document specifies the configurations, prompts, and system roles of the agents constituting the Research Consensus Council.

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
