import type { AppView } from '../lib/api';
import { LandingHeroOrbit } from '../components/LandingHeroOrbit';

interface LandingViewProps {
  onEnterPortal: (view?: AppView) => void;
}

export function LandingView({ onEnterPortal }: LandingViewProps) {
  return (
    <div className="landing">
      <div className="landing-bg-grid" aria-hidden />
      <div className="landing-bg-glow" aria-hidden />

      <nav className="landing-nav">
        <div className="landing-brand">RCC</div>
        <div className="landing-nav-links">
          <a href="#protocol">Methodology</a>
          <a href="#ethics">AI Council</a>
          <a href="#ethics">Ethics</a>
          <button type="button" className="landing-nav-link-btn" onClick={() => onEnterPortal('docs')}>
            Documentation
          </button>
        </div>
        <button
          type="button"
          className="landing-btn landing-btn-solid"
          data-testid="access-portal-btn"
          onClick={() => onEnterPortal('council')}
        >
          Access Portal
        </button>
      </nav>

      <header className="landing-hero">
        <div className="landing-hero-copy">
          <h1 className="landing-fade stagger-1">Research Consensus Council</h1>
          <p className="landing-tagline landing-fade stagger-2">
            Five specialized AI reviewers. One transparent scientific consensus.
          </p>
          <p className="landing-lede landing-fade stagger-3">
            A multi-agent council for rigorous academic synthesis. Point it at a manuscript and watch
            domain-specific agents debate, score, and converge—with human-in-the-loop gates.
          </p>
          <div className="landing-cta-row landing-fade stagger-4">
            <button
              type="button"
              className="landing-btn landing-btn-solid"
              data-testid="start-validation-btn"
              onClick={() => onEnterPortal('research')}
            >
              Start Validation
            </button>
            <a className="landing-btn landing-btn-ghost" href="#protocol">
              Explore Architecture
            </a>
          </div>
          <div className="landing-chips landing-fade stagger-5">
            <span className="landing-chip">Multi-Agent AI</span>
            <span className="landing-chip">Research Validation</span>
            <span className="landing-chip">Consensus Scoring</span>
            <span className="landing-chip">Transparent Reports</span>
          </div>
        </div>
        <LandingHeroOrbit />
      </header>

      <section className="landing-section" id="protocol">
        <div className="landing-section-head">
          <h2>The Synthesis Protocol</h2>
          <p>A multi-stage pipeline that extracts content, runs five reviewers, and produces a scored verdict.</p>
        </div>
        <ol className="landing-timeline">
          <li>
            <span className="landing-timeline-node" />
            <div>
              <h3>Upload research paper</h3>
              <p>Upload a PDF or text manuscript, or point Research at a local path / recent archive paper.</p>
            </div>
          </li>
          <li>
            <span className="landing-timeline-node" />
            <div>
              <h3>Extract content</h3>
              <p>Parse abstract, methods, results, claims, tables, and citations for grounding.</p>
            </div>
          </li>
          <li>
            <span className="landing-timeline-node" />
            <div>
              <h3>Activate AI council</h3>
              <p>
                Skeptical Reviewer, Method Evaluator, Domain Expert, Ethics Officer, and Industry
                Translator deliberate across three rounds with HITL approval.
              </p>
            </div>
          </li>
        </ol>
      </section>

      <section className="landing-section landing-ethics" id="ethics">
        <div className="landing-section-head">
          <h2>Ethics & integrity</h2>
          <p>
            The Ethics Officer owns fairness, privacy, and integrity scoring. Claim grounding flags
            ungrounded statements so the council does not treat unsupported claims as evidence.
          </p>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="landing-brand">RCC</div>
        <div className="landing-footer-meta">
          Self-hosted research review · © {new Date().getFullYear()} Research Consensus Council
        </div>
      </footer>
    </div>
  );
}
