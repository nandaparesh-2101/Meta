"""Master Orchestrator.

Responsibilities (per the system spec):

1. Receive user/business/data request (as a pre-built `AgentContext`).
2. Determine the problem type (`context.trigger`).
3. Select relevant agents (`router.route_for_trigger`).
4. Execute agents in logical order.
5. Combine outputs (`context.findings`).
6. Resolve contradictions (handled inside `OptimizationAgent`, preserved not discarded).
7. Identify root cause (diagnostic agents run before optimization).
8. Check data sufficiency (baked into every finding + Guardian's own check).
9. Send recommendations through Guardian.
10. Produce final command-center report.
11. Save important learnings/audit/experiments to memory.

This orchestrator does NOT blindly call every agent — `router.py` selects a
relevant diagnostic subset per trigger.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents import AGENT_REGISTRY, GuardianAgent
from app.execution.approval import create_approval_request
from app.llm.provider import LLMProvider, get_llm_provider
from app.memory.experiments import ExperimentMemory
from app.memory.store import MemoryStore
from app.models.execution import ApprovalRequest, AuditEventType, GuardianDecision
from app.orchestration.context import AgentContext
from app.orchestration.router import route_for_trigger

ALWAYS_FIRST = "business_intelligence"
ALWAYS_BEFORE_GUARDIAN = ["experimentation", "optimization"]


@dataclass
class WorkflowResult:
    context: AgentContext
    guardian_decisions: list[GuardianDecision] = field(default_factory=list)
    approval_requests: list[ApprovalRequest] = field(default_factory=list)
    executed_agents: list[str] = field(default_factory=list)


class Orchestrator:
    def __init__(self, memory: MemoryStore | None = None, llm_provider: LLMProvider | None = None) -> None:
        self.memory = memory or MemoryStore()
        self.llm = llm_provider or get_llm_provider()

    def run(self, context: AgentContext) -> WorkflowResult:
        self.memory.record(
            AuditEventType.ANALYSIS_STARTED,
            actor="orchestrator",
            summary=f"Analysis started (trigger={context.trigger})",
            details={"trigger": context.trigger},
        )

        context.existing_experiments = self.memory.get_all_experiments()

        executed_agents: list[str] = []

        # Step 1: business context always establishes the frame first.
        self._run_agent(ALWAYS_FIRST, context)
        executed_agents.append(ALWAYS_FIRST)

        # Step 2: intelligent routing — only the diagnostic agents relevant
        # to this trigger run, in order.
        for agent_name in route_for_trigger(context.trigger):
            self._run_agent(agent_name, context)
            executed_agents.append(agent_name)

        # Step 3: competitor intelligence only activates when research was
        # actually supplied — never invented, never skipped silently either
        # (it self-reports "no external data" when nothing was given).
        if context.competitor_research:
            self._run_agent("competitor_intelligence", context)
            executed_agents.append("competitor_intelligence")

        # Step 4: experimentation converts hypotheses raised above into
        # pre-registered, deduplicated experiments.
        self._run_agent("experimentation", context)
        executed_agents.append("experimentation")
        for experiment in context.new_experiments:
            experiment_memory = ExperimentMemory(self.memory)
            experiment_memory.register(experiment)

        # Step 5: optimization converts findings into recommendations.
        self._run_agent("optimization", context)
        executed_agents.append("optimization")
        for recommendation in context.recommendations:
            self.memory.save_recommendation(recommendation)

        # Step 6: every finding produced this run is persisted to memory.
        for finding in context.findings:
            self.memory.save_finding(finding)

        # Step 7: Guardian reviews every recommendation; nothing is approved
        # or executed without passing through here first.
        guardian = GuardianAgent(llm_provider=self.llm, audit=self.memory)
        decisions = guardian.review(context, context.recommendations)
        for decision in decisions:
            self.memory.save_guardian_decision(decision)

        # Step 8: approval requests are created for anything Guardian did not
        # reject and that the recommendation itself flags as needing one.
        approval_requests: list[ApprovalRequest] = []
        rec_by_id = {r.recommendation_id: r for r in context.recommendations}
        for decision in decisions:
            rec = rec_by_id.get(decision.recommendation_id)
            if rec is None:
                continue
            approval = create_approval_request(rec, decision)
            if approval is not None:
                self.memory.save_approval(approval)
                self.memory.record(
                    AuditEventType.APPROVAL_REQUESTED,
                    actor="orchestrator",
                    summary=f"Approval requested for {rec.recommendation_id} ({rec.action.value})",
                    entity_id=rec.entity_id,
                )
                approval_requests.append(approval)

        self.memory.record(
            AuditEventType.ANALYSIS_COMPLETED,
            actor="orchestrator",
            summary=(
                f"Analysis completed: {len(executed_agents)} agent(s) run, "
                f"{len(context.recommendations)} recommendation(s), {len(decisions)} guardian decision(s)"
            ),
            details={"executed_agents": executed_agents},
        )

        return WorkflowResult(
            context=context,
            guardian_decisions=decisions,
            approval_requests=approval_requests,
            executed_agents=executed_agents,
        )

    def _run_agent(self, agent_name: str, context: AgentContext) -> None:
        agent_cls = AGENT_REGISTRY.get(agent_name)
        if agent_cls is None:
            return
        agent = agent_cls(llm_provider=self.llm, audit=self.memory)
        agent.run(context)
