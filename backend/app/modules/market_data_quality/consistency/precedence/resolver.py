"""
M03.06.04 - Source Precedence and Conflict Resolution Manager.
Resolves conflicts using effective-dated precedence rules and provides auditable manual overrides.
"""

import uuid
from decimal import Decimal
from typing import Optional, Dict, Any, Tuple
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.market_data_quality.consistency.models import (
    SourcePrecedenceRule,
    ConsistencyConflict,
    ConsistencyResolutionHistory,
)
from backend.app.modules.market_data_quality.consistency.schemas import (
    ObservationComparisonInput,
    ConflictResolutionActionRequest,
)


class PrecedenceResolver:
    """
    Evaluates source ranking to resolve data discrepancies automatically.
    """

    @classmethod
    async def get_effective_rule(
        cls,
        session: AsyncSession,
        exchange: str,
        provider_id: str,
        instrument_id: Optional[str] = None,
        observation_type: str = "ALL"
    ) -> Optional[SourcePrecedenceRule]:
        stmt = select(SourcePrecedenceRule).where(
            and_(
                SourcePrecedenceRule.exchange == exchange,
                SourcePrecedenceRule.provider_id == provider_id,
                SourcePrecedenceRule.enabled == True
            )
        )
        res = await session.execute(stmt)
        rules = res.scalars().all()
        if not rules:
            return None

        # Prioritize instrument specific rule over generic rule
        for r in rules:
            if instrument_id and r.instrument_id == instrument_id:
                return r
        for r in rules:
            if not r.instrument_id:
                return r
        return rules[0]

    @classmethod
    async def attempt_auto_resolution(
        cls,
        session: AsyncSession,
        exchange: str,
        source_a: ObservationComparisonInput,
        source_b: ObservationComparisonInput,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Attempts to resolve between Source A and Source B using source precedence.
        Returns (winner_source, winner_observation_id, rule_code).
        """
        rule_a = await cls.get_effective_rule(session, exchange, source_a.provider_id, source_a.instrument_id)
        rule_b = await cls.get_effective_rule(session, exchange, source_b.provider_id, source_b.instrument_id)

        if not rule_a or not rule_b:
            return None, None, None

        # Lower priority integer = higher precedence (1 > 2)
        if rule_a.priority < rule_b.priority:
            return source_a.provider_id, source_a.observation_id, rule_a.rule_code
        elif rule_b.priority < rule_a.priority:
            return source_b.provider_id, source_b.observation_id, rule_b.rule_code

        # Equal priority -> cannot auto-resolve
        return None, None, None
