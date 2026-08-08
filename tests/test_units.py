import asyncio
import sys
import unittest
from pathlib import Path

# Add root folder to search path
sys.path.insert(0, str(Path(__file__).parent.parent))

from circuit import CircuitBreaker
from config import settings
from council import ScoreCalculator, determine_verdict


class TestConsensusCouncilUnits(unittest.TestCase):
    def test_determine_verdict_thresholds(self):
        """Verify verdicts mapped according to aggregated scores."""
        self.assertEqual(determine_verdict(4.9), "Accept")
        self.assertEqual(determine_verdict(4.5), "Accept")
        self.assertEqual(determine_verdict(4.49), "Minor Revisions")
        self.assertEqual(determine_verdict(3.5), "Minor Revisions")
        self.assertEqual(determine_verdict(3.49), "Major Revisions")
        self.assertEqual(determine_verdict(2.5), "Major Revisions")
        self.assertEqual(determine_verdict(2.49), "Reject")
        self.assertEqual(determine_verdict(1.0), "Reject")

    def test_score_calculator_weighted_sum(self):
        """Verify ScoreCalculator computes strict dot products."""
        weights = {
            "Clarity & Presentation": 0.20,
            "Methodology Rigor":      0.25,
            "Novelty & Significance": 0.20,
            "Ethics & Integrity":     0.20,
            "Practical Impact":       0.15,
        }
        scores = {
            "Clarity & Presentation": 4.0,
            "Methodology Rigor":      5.0,
            "Novelty & Significance": 3.0,
            "Ethics & Integrity":     4.0,
            "Practical Impact":       2.0,
        }
        # Calculation: 4*0.2 + 5*0.25 + 3*0.2 + 4*0.2 + 2*0.15 = 0.8 + 1.25 + 0.6 + 0.8 + 0.3 = 3.75
        result = ScoreCalculator.compute(weights, scores)
        self.assertEqual(result, 3.75)

    def test_settings_validation_loaded(self):
        """Verify Settings loaded and validated successfully."""
        self.assertEqual(settings.llm_provider, "stub")
        self.assertEqual(settings.openai_api_key, "dummy_openai_key")

    def test_table_padding_formatter(self):
        """Verify table formatting padding cell values correctly."""
        from council import _format_table
        tbl = [["Col1", "Col2"], ["A", "B"]]
        formatted = _format_table(tbl)
        self.assertIn("Col1", formatted)
        self.assertIn(" | ", formatted)

    def test_citation_regex_parser(self):
        """Verify citation strings are captured by regex patterns."""
        from council import _extract_citations
        text = "Check works of [1] and (Smith, 2024) or Jones et al. (2020)."
        citations = _extract_citations(text)
        self.assertIn("[1]", citations)
        self.assertIn("(Smith, 2024)", citations)
        self.assertIn("Jones et al. (2020)", citations)

    def test_circuit_breaker_failover(self):
        """Verify CircuitBreaker state transitions (Closed -> Open -> Half-Open)."""
        async def run_async_test():
            # Failure threshold = 2, recovery timeout = 1 second
            breaker = CircuitBreaker(failure_threshold=2, recovery_timeout=1)

            # Initial state
            self.assertEqual(await breaker.get_state(), "Closed")

            # Record first failure
            await breaker.record_failure()
            self.assertEqual(await breaker.get_state(), "Closed")

            # Record second failure (reaches threshold)
            await breaker.record_failure()
            self.assertEqual(await breaker.get_state(), "Open")

            # Sleep 1.1s to allow recovery timeout cooldown to expire
            await asyncio.sleep(1.1)
            self.assertEqual(await breaker.get_state(), "Half-Open")

            # Record success (resets to closed)
            await breaker.record_success()
            self.assertEqual(await breaker.get_state(), "Closed")

        asyncio.run(run_async_test())

    def test_prior_art_validator_query(self):
        """Verify PriorArtValidator returns properly structured query result."""
        from skills.prior_art_validator import PriorArtValidator
        validator = PriorArtValidator()
        res = validator.query_prior_art("quantum computing methodology", n_results=2)
        self.assertIn("status", res)
        self.assertIn("findings", res)

    def test_db_appeals_and_frame_cleanup(self):
        """Verify DB appeal insertion/retrieval and async websocket frame cleanup."""
        import db
        db.init_db()
        paper_id = db.save_paper("tests/fixtures/test_paper.txt", "hash123", "abstract", "methods", "results", "claims", "full")
        appeal_id = db.insert_appeal(paper_id, "Rebuttal claim")
        db.update_appeal_verdict(appeal_id, "Accept")

        appeals = db.get_appeals_by_paper(paper_id)
        self.assertTrue(len(appeals) > 0)
        self.assertEqual(appeals[0]["new_verdict"], "Accept")

        async def test_async_cleanup():
            app_db = await db.init_db_async("test_council.db")
            await db.log_frame(app_db, paper_id, 1, '{"type": "token"}')
            frames = await db.get_websocket_frames("test_council.db", paper_id, 0)
            self.assertTrue(len(frames) >= 1)
            await db.cleanup_websocket_frames(app_db, paper_id, max_age_seconds=0)
            await app_db.close()

        asyncio.run(test_async_cleanup())

    def test_extract_content_missing_file(self):
        """Missing manuscript must raise FileNotFoundError before LLM work."""
        from council import extract_content
        with self.assertRaises(FileNotFoundError):
            extract_content("tests/fixtures/does_not_exist.pdf")

    def test_extract_content_short_txt_sections(self):
        """Short .txt papers must still populate methods/results (not only abstract)."""
        from council import extract_content
        p = extract_content("tests/fixtures/paper_grounded.txt")
        self.assertIn("transformer attention", p.methods.lower())
        self.assertIn("casp14", p.results.lower())
        self.assertTrue(p.claims.strip())

    def test_safe_print_survives_broken_stderr(self):
        """Windows API hosts can have invalid stderr (Errno 22); stub banner must not abort."""
        import sys
        from council import _safe_print, _should_prompt

        class Broken:
            def write(self, _s):
                raise OSError(22, "Invalid argument")

            def flush(self):
                pass

        old = sys.stderr
        try:
            sys.stderr = Broken()
            _safe_print("SIMULATED banner", file=sys.stderr)
        finally:
            sys.stderr = old

        class BrokenStdin:
            def isatty(self):
                raise OSError(22, "Invalid argument")

        old_in = sys.stdin
        try:
            sys.stdin = BrokenStdin()
            self.assertFalse(_should_prompt())
        finally:
            sys.stdin = old_in

    def test_submit_appeal_rejects_empty_rebuttal(self):
        """Empty rebuttal is a client error, not a silent re-deliberation."""
        from council import submit_appeal
        result = submit_appeal("any.pdf", "   ")
        self.assertIn("error", result)
        self.assertIn("Rebuttal", result["error"])

    def test_jina_client_skips_without_key(self):
        """Without JINA_API_KEY, embed/rerank soft-skip (no network)."""
        from skills.retrieval.jina_client import JinaClient
        client = JinaClient(api_key="")
        emb = client.embed(["hello world"])
        self.assertEqual(emb["status"], "skipped")
        self.assertEqual(emb["embeddings"], [])
        rr = client.rerank("q", ["doc a", "doc b"])
        self.assertEqual(rr["status"], "skipped")

    def test_jina_embed_mock_success(self):
        """Mocked httpx response yields success embeddings."""
        from unittest.mock import MagicMock, patch
        from skills.retrieval.jina_client import JinaClient

        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]
        }
        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = False
        mock_client.post.return_value = mock_resp

        with patch("skills.retrieval.jina_client.httpx.Client", return_value=mock_client):
            client = JinaClient(api_key="test-key")
            emb = client.embed(["a", "b"])
        self.assertEqual(emb["status"], "success")
        self.assertEqual(len(emb["embeddings"]), 2)

    def test_review_skill_tree_claim_grounding(self):
        """Review tree returns claim_grounding with grounded/ungrounded flags."""
        from council import PaperContent
        from skills import run_skill_tree

        paper = PaperContent(
            file_path="t.txt",
            content_hash="x",
            abstract="We study neural ranking for scientific claims with strong evidence.",
            methods="We trained a neural ranking model on annotated scientific claims.",
            results="The neural ranking model improved nDCG on the held-out set.",
            claims="Our neural ranking model improves claim verification accuracy substantially.",
            full_text="filler",
        )
        out = run_skill_tree("review", paper=paper)
        self.assertEqual(out["mode"], "review")
        ids = [s["skill_id"] for s in out["skills"]]
        self.assertIn("review.claim_grounding", ids)
        cg = next(s for s in out["skills"] if s["skill_id"] == "review.claim_grounding")
        self.assertEqual(cg["status"], "success")
        self.assertTrue(any(f.get("grounded") for f in cg["findings"] if isinstance(f, dict) and "claim" in f))

    def test_claim_grounding_ungrounded_without_methods_results(self):
        """Claims only in claims/abstract (not methods/results) must be ungrounded."""
        from council import PaperContent
        from skills.review.claim_grounding import run_claim_grounding

        paper = PaperContent(
            file_path="t.txt",
            content_hash="x",
            abstract="Placeholder abstract text that is long enough to parse as content.",
            methods="",
            results="",
            claims="This revolutionary approach completely transforms structural biology overnight.",
            full_text="This revolutionary approach completely transforms structural biology overnight.",
        )
        res = run_claim_grounding(paper)
        claim_findings = [f for f in res.findings if isinstance(f, dict) and f.get("claim")]
        self.assertTrue(claim_findings)
        self.assertTrue(all(not f.get("grounded") for f in claim_findings))

    def test_claim_grounding_supported_from_methods(self):
        """Claim echoed in methods (not only full_text) is supported."""
        from council import PaperContent
        from skills.agent_tools import dispatch_tool

        paper = PaperContent(
            file_path="t.txt",
            content_hash="x",
            abstract="",
            methods="We apply transformer attention over residue graphs for folding prediction.",
            results="Accuracy reached ninety percent on the CASP14 benchmark suite.",
            claims="We apply transformer attention over residue graphs for folding prediction with strong gains.",
            full_text="",
        )
        out = dispatch_tool("query_claim_grounding", {}, paper=paper)
        self.assertEqual(out["status"], "success")
        self.assertTrue(any(f.get("grounded") for f in out["findings"] if isinstance(f, dict)))

    def test_build_prompt_includes_skill_context(self):
        """Agents receive SKILL CONTEXT block when review findings are formatted."""
        from council import AGENTS, PaperContent, _format_skill_context, build_prompt

        paper = PaperContent(
            file_path="t.txt", content_hash="x",
            abstract="a" * 60, methods="m" * 60, results="r" * 60, claims="c" * 60, full_text="t",
        )
        skill_findings = {
            "review": {
                "skills": [{
                    "skill_id": "review.claim_grounding",
                    "message": "0/1 claims grounded",
                    "findings": [{
                        "claim": "Ungrounded megaclaim about curing all disease immediately.",
                        "grounded": False,
                        "confidence": "ungrounded",
                    }],
                }],
            }
        }
        ctx = _format_skill_context(skill_findings)
        self.assertIn("UNGROUNDED", ctx)
        prompt = build_prompt(AGENTS[0], paper, 1, skill_context=ctx)
        self.assertIn("SKILL CONTEXT", prompt)
        self.assertIn("UNGROUNDED", prompt)

    def test_agent_tools_registry(self):
        from skills.agent_tools import TOOL_SCHEMAS, list_tool_names
        names = list_tool_names()
        self.assertIn("query_claim_grounding", names)
        self.assertIn("query_prior_art", names)
        self.assertEqual(len(TOOL_SCHEMAS), 2)

    def test_rerank_passthrough_without_jina(self):
        from skills.retrieval.jina_client import JinaClient
        from skills.retrieval.rerank import rerank_documents
        res = rerank_documents("q", ["alpha", "beta", "gamma"], top_n=2, client=JinaClient(api_key=""))
        self.assertIn(res["status"], ("skipped", "success", "error"))
        self.assertEqual(len(res["findings"]), 2)

if __name__ == "__main__":
    unittest.main()
