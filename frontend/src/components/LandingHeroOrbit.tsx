import type { CSSProperties } from 'react';
import { COUNCIL_AGENTS } from '../lib/agents';

const COLORS = ['#a78bfa', '#22d3ee', '#60a5fa', '#34d399', '#fb923c'];

export function LandingHeroOrbit() {
  const n = COUNCIL_AGENTS.length;

  return (
    <div className="landing-hero-orbit" data-testid="landing-hero-orbit" aria-hidden>
      {/* Dashed circle ring (visual only) */}
      <div className="landing-orbit-ring" />

      {/* Each card has an outer positioner (orbits) and inner card (counter-rotates to stay upright) */}
      {COUNCIL_AGENTS.map((agent, i) => {
        const angle = (i * 360) / n; // degrees
        return (
          <div
            key={agent.name}
            className="landing-orbit-pos"
            style={{ '--start-angle': `${angle}deg`, '--accent': COLORS[i % COLORS.length] } as CSSProperties}
          >
            <div
              className="landing-orbit-card"
              style={{ '--counter-angle': `${-angle}deg` } as CSSProperties}
            >
              <span className="landing-orbit-name">{agent.short}</span>
              <span className="landing-orbit-crit">{agent.criterion}</span>
            </div>
          </div>
        );
      })}

      <div className="landing-paper-stub">
        <div className="landing-paper-title">Multi-Agent Consensus</div>
        <div className="landing-paper-line" />
        <div className="landing-paper-line short" />
        <div className="landing-paper-line" />
        <div className="landing-paper-line med" />
        <div className="landing-paper-badge">VERIFIED</div>
      </div>
      <div className="landing-consensus-toast pulse-notification">
        <span className="landing-toast-dot" />
        <div>
          <p className="landing-toast-title">Consensus Ready</p>
          <p className="landing-toast-id">DOC_ID: demo</p>
        </div>
      </div>
    </div>
  );
}
