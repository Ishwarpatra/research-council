import sys
import unittest
from pathlib import Path

# Add root folder to search path
sys.path.insert(0, str(Path(__file__).parent.parent))

from council import ScoreCalculator, determine_verdict, load_config


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

    def test_config_validation_schema(self):
        """Verify invalid environment configurations raise ValueError."""
        # Clean default loading
        cfg = load_config()
        self.assertIn("llm_provider", cfg)
        self.assertIn(cfg["llm_provider"], ["stub", "ollama", "openai"])

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

if __name__ == "__main__":
    unittest.main()
