# Research Consensus Council (RCC)

Multi-agent deliberation consensus system with persistence, real LLM hooks, appeals processing, and web/dashboard visualisations.

## Setup & Ingestion

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Configure settings:
   - System reads environment variables:
     - `RCC_LLM_PROVIDER`: `stub` (default), `ollama`, or `openai`.
     - `OLLAMA_HOST`: host URI (defaults to `http://localhost:11434`).
     - `OPENAI_API_KEY`: API key for OpenAI GPT execution.
     - `RCC_WEBHOOK_URL`: endpoint for receiving deliberation alerts.
   - Alternatively, place a `council_config.json` in the root folder containing custom weights or mapping keys.

## Usage

- **Run Consensus Deliberation:**
  ```bash
  python council.py <paper.pdf>
  ```
- **Submit Appeal:**
  ```bash
  python council.py --appeal <paper.pdf> "rebuttal text here"
  ```
- **Run Quality Audit:**
  ```bash
  python council.py --audit
  ```
- **Review Paper Deliberation History:**
  ```bash
  python council.py --history <paper.pdf>
  ```
- **Start HTTP API Server & Live Dashboard:**
  ```bash
  python council.py --api
  ```
  Once running, view the dashboard at `http://127.0.0.1:8080/`.

## REST API Endpoints

- `GET /api/papers`: Returns all processed papers.
- `GET /api/reviews?path=<path>`: Returns all 3 rounds of review history for a paper.
- `GET /api/deliberation?path=<path>`: Returns final verdict, aggregate scores, and parsed report.
- `GET /api/settings`: Read current server configurations.
- `POST /api/settings`: Modify criterion weights live (JSON: `{"weights": {...}}`). Weights must sum to 1.0.
- `GET /api/audit`: Returns monthly quality control statistics.