import { COUNCIL_AGENTS, type AgentStatus } from '../lib/agents';
import { paperBasename } from '../lib/api';

export interface AgentRuntimeState {
  name: string;
  status: AgentStatus;
  challenge?: string | null;
  score?: number | null;
  justification?: string | null;
}

interface AgentFlowBoardProps {
  paperPath?: string | null;
  abstractText?: string;
  agentStates: AgentRuntimeState[];
}

export function AgentFlowBoard({ paperPath, abstractText, agentStates }: AgentFlowBoardProps) {
  const byName = Object.fromEntries(agentStates.map((a) => [a.name, a]));
  const challenge = agentStates.find((a) => a.challenge);

  return (
    <div className="panel-card">
      <div className="agent-flow">
        <div className="paper-source-card">
          <h3>Input source</h3>
          <div className="title">{paperPath ? paperBasename(paperPath) : 'No paper selected'}</div>
          <div className="meta">{paperPath ? paperBasename(paperPath) : 'Choose Archive or start Research'}</div>
          {abstractText ? <p className="abstract">{abstractText}</p> : null}
        </div>

        <div className="flow-stage">
          <div className="orchestrator-chip" title="3 rounds + HITL gate">
            RCC Orchestrator · routing reviewers
          </div>

          <div className="agent-board" data-testid="agent-board">
            {COUNCIL_AGENTS.map((agent) => {
              const st = byName[agent.name]?.status || 'awaiting';
              return (
                <div
                  key={agent.name}
                  className={`agent-chip ${st}`}
                  data-testid={`agent-${agent.short.toLowerCase()}`}
                >
                  <div className="name">{agent.name}</div>
                  <div className="status">
                    {st === 'active' ? 'Active' : st}
                    {byName[agent.name]?.score != null ? ` · ${byName[agent.name].score}/5` : ''}
                  </div>
                  {byName[agent.name]?.challenge ? (
                    <div className="challenge-tip">
                      Challenging: {byName[agent.name].challenge}
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>

          {challenge?.justification ? (
            <div className="challenge-tip">
              “{String(challenge.justification).slice(0, 180)}”
              {String(challenge.justification).length > 180 ? '…' : ''} — {challenge.name}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
