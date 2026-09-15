"""Agent 10 — Experimentation.

Converts other agents' hypotheses (tagged findings like
`copy_test_candidate` or `creative_pattern`) into fully-specified,
pre-registered experiments. Before proposing a new experiment it checks
`context.existing_experiments` for the same hypothesis/variable and refuses
to duplicate an already-tested one unless materially different.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.experiments import Experiment, ExperimentStatus
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext
from app.rules.safety_rules import check_duplicate_experiment

EXPERIMENT_TRIGGER_TAGS = {"copy_test_candidate", "creative_pattern"}


class ExperimentationAgent(BaseAgent):
    name = "experimentation"
    description = "Builds controlled, pre-registered A/B experiments from other agents' hypotheses."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        findings: list[AgentFinding] = []
        candidates = [f for f in context.findings if EXPERIMENT_TRIGGER_TAGS & set(f.tags)]

        for candidate in candidates:
            experiment = self._build_experiment(candidate)
            duplicate_concerns = check_duplicate_experiment(experiment, context.existing_experiments)

            if duplicate_concerns:
                findings.append(
                    AgentFinding(
                        agent_name=self.name,
                        entity_id=candidate.entity_id,
                        headline=f"Skipped duplicate experiment for {candidate.entity_id}",
                        detail=(
                            "A materially identical experiment already exists; not creating a duplicate. "
                            + " ".join(duplicate_concerns)
                        ),
                        evidence=duplicate_concerns,
                        data_sufficiency=candidate.data_sufficiency,
                        confidence=0.9,
                        suggested_actions=[ActionType.DO_NOTHING],
                        tags=["duplicate_experiment_prevented"],
                    )
                )
                continue

            context.new_experiments.append(experiment)
            findings.append(
                AgentFinding(
                    agent_name=self.name,
                    entity_id=candidate.entity_id,
                    headline=f"New experiment proposed: {experiment.hypothesis}",
                    detail=(
                        f"Variable: {experiment.variable}. Control: {experiment.control_description}. "
                        f"Test: {experiment.test_description}. Success metric: {experiment.success_metric}. "
                        f"Minimum data: {experiment.minimum_data_requirement}. "
                        f"Decision rule: {experiment.decision_rule}."
                    ),
                    evidence=[f"Derived from finding: {candidate.headline}"],
                    data_sufficiency=candidate.data_sufficiency,
                    confidence=0.6,
                    suggested_actions=[ActionType.LAUNCH_TEST],
                    tags=["experiment_created"],
                )
            )

        return findings

    def _build_experiment(self, finding: AgentFinding) -> Experiment:
        variable = "copy" if "copy_test_candidate" in finding.tags else "creative_angle_format"
        hypothesis = (
            f"Changing {variable} for entity {finding.entity_id} will improve conversion efficiency, "
            f"based on: {finding.headline}"
        )
        return Experiment(
            experiment_id=self.new_id("exp"),
            hypothesis=hypothesis,
            variable=variable,
            control_description=f"Current live version of {finding.entity_id}",
            test_description=f"New {variable} variant addressing: {finding.headline}",
            success_metric="CPL and qualified CPL",
            minimum_data_requirement="50 leads per arm or 14 days per arm, whichever is reached first",
            decision_rule=(
                "Declare the test variant a winner only if it improves qualified CPL by >= 10% "
                "AND the minimum data requirement is met; otherwise inconclusive."
            ),
            review_window_days=14,
            related_entity_ids=[finding.entity_id] if finding.entity_id else [],
            status=ExperimentStatus.PLANNED,
        )
