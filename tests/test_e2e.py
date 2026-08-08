import json
import threading
import time
import unittest
import urllib.request
from pathlib import Path

# Try to import Playwright for E2E tests, fallback if not installed
try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

class TestConsensusCouncilE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Dynamically import and run the API server in a background thread
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from council import start_api_server

        # Run server on port 8081 to prevent clashes with port 8080
        cls.server_thread = threading.Thread(
            target=start_api_server,
            args=("127.0.0.1", 8081),
            daemon=True
        )
        cls.server_thread.start()
        time.sleep(1.5)  # allow server to bind

    def test_api_settings_get(self):
        """Verify settings GET returns configured weights."""
        req = urllib.request.Request("http://127.0.0.1:8081/api/settings")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("weights", data)
            self.assertIn("db_path", data)

    def test_api_settings_post_validation(self):
        """Verify settings POST rejects invalid weight sums."""
        payload = {
            "weights": {
                "Clarity & Presentation": 0.1,
                "Methodology Rigor":      0.1,
                "Novelty & Significance": 0.1,
                "Ethics & Integrity":     0.1,
                "Practical Impact":       0.1
            }
        }
        req = urllib.request.Request(
            "http://127.0.0.1:8081/api/settings",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 400)
        err_msg = json.loads(ctx.exception.read().decode())
        self.assertIn("error", err_msg)

    def test_api_prior_art_get(self):
        """Verify GET /api/prior_art endpoint executes semantic search."""
        req = urllib.request.Request("http://127.0.0.1:8081/api/prior_art?query=test")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            self.assertIn("status", data)
            self.assertIn("findings", data)

    def test_playwright_dashboard_navigation(self):
        """Playwright test: navigate dashboard, check visual headings."""
        if not HAS_PLAYWRIGHT:
            self.skipTest("Playwright library is not installed in the current environment.")

        with sync_playwright() as p:
            # Headless browser navigation
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto("http://127.0.0.1:8081/")
                # Verify header title is present and visible
                header_text = page.locator("header h1").text_content()
                self.assertIn("Research Consensus Council", header_text)

                # Check list has loading text or loaded entries
                aside_text = page.locator("aside").text_content()
                self.assertIn("Processed Papers", aside_text)
            finally:
                browser.close()

if __name__ == "__main__":
    unittest.main()
