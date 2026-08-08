export type AgentStatus = 'awaiting' | 'reviewing' | 'active' | 'done';

export interface CouncilAgent {
  name: string;
  criterion: string;
  short: string;
}

/** Mirrors council.py AGENTS (display only). */
export const COUNCIL_AGENTS: CouncilAgent[] = [
  { name: 'Skeptical Reviewer', criterion: 'Clarity & Presentation', short: 'Skeptical' },
  { name: 'Method Evaluator', criterion: 'Methodology Rigor', short: 'Methodologist' },
  { name: 'Domain Expert', criterion: 'Novelty & Significance', short: 'Domain' },
  { name: 'Ethics Officer', criterion: 'Ethics & Integrity', short: 'Ethics' },
  { name: 'Industry Translator', criterion: 'Practical Impact', short: 'Translator' },
];
