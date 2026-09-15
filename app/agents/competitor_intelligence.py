"""Agent 14 — Competitor Intelligence.

Only activates when external research is actually supplied via
`context.competitor_research` — this build performs no live web research.
When research snippets are present, extracts simple recurring-keyword
patterns (positioning, offers, hooks). Never recommends copying a
competitor outright.
"""

from __future__ import annotations

import re
from collections import Counter

from app.agents.base import BaseAgent
from app.models.metrics import DataSufficiencyLevel
from app.models.recommendations import ActionType, AgentFinding
from app.orchestration.context import AgentContext

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "is", "are",
    "our", "your", "we", "you", "on", "at", "by", "it", "this", "that", "as",
}


class CompetitorIntelligenceAgent(BaseAgent):
    name = "competitor_intelligence"
    description = "Analyzes supplied competitor research for positioning, offer and messaging patterns."

    def analyze(self, context: AgentContext) -> list[AgentFinding]:
        if not context.competitor_research:
            return [
                AgentFinding(
                    agent_name=self.name,
                    entity_id=None,
                    headline="No competitor research supplied for this run.",
                    detail=(
                        "This build does not perform live external research. Supply research snippets via "
                        "`AgentContext.competitor_research` to activate this agent."
                    ),
                    evidence=[],
                    data_sufficiency=DataSufficiencyLevel.INSUFFICIENT_DATA,
                    confidence=0.0,
                    suggested_actions=[],
                    tags=["no_external_data"],
                )
            ]

        word_counts: Counter = Counter()
        for snippet in context.competitor_research:
            words = re.findall(r"[a-zA-Z']+", snippet.lower())
            word_counts.update(w for w in words if w not in STOPWORDS and len(w) > 3)

        common = word_counts.most_common(8)
        evidence = [f"'{word}' appears {count}x across supplied research" for word, count in common]

        return [
            AgentFinding(
                agent_name=self.name,
                entity_id=None,
                headline="Recurring themes identified across supplied competitor research.",
                detail=(
                    "These are descriptive patterns only. Do not copy competitor messaging directly — use "
                    "them as market-gap and positioning hypotheses for the Copy/Offer agents to test."
                ),
                evidence=evidence,
                data_sufficiency=(
                    DataSufficiencyLevel.EARLY_SIGNAL
                    if len(context.competitor_research) < 5
                    else DataSufficiencyLevel.PROMISING
                ),
                confidence=0.4,
                suggested_actions=[ActionType.DO_NOTHING],
                tags=["competitor_pattern"],
            )
        ]
