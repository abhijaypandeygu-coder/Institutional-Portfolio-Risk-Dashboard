"""
M06.06 Concentration Analytics Service.

Coordinates concentration calculations, HHI, top-N cumulative concentration ratios,
effective number of equally weighted groups, cross-dimension aggregations (instrument,
issuer, sector, industry, country, region), trend analysis, and policy threshold evaluation.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.modules.risk_management.concentration_analytics.models import (
    ConcentrationResult,
    ConcentrationContributor,
    ConcentrationComparison,
    ConcentrationPolicy,
    ConcentrationGroupingDimension,
    ConcentrationExposureBasis,
    ConcentrationCalculationStatus,
    ConcentrationTrendStatus,
    ConcentrationInterpretationLevel,
)
from backend.app.modules.risk_management.concentration_analytics.schemas import (
    ConcentrationCalculateRequest,
    ConcentrationSummaryResponse,
    ConcentrationContributorItemResponse,
    ConcentrationRatiosResponse,
    ConcentrationHHIResponse,
    ConcentrationComparisonResponse,
    ConcentrationPolicyCreateRequest,
    ConcentrationPolicyResponse,
)
from backend.app.modules.risk_management.concentration_analytics.repositories.repository import (
    ConcentrationRepository,
)

# Authoritative upstream integrations
from backend.app.modules.risk_management.instrument_exposure.services.service import (
    InstrumentExposureService,
)
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
)
from backend.app.modules.risk_management.sector_exposure.services.service import (
    SectorExposureService,
)
from backend.app.modules.risk_management.sector_exposure.schemas import (
    SectorExposureCalculateRequest,
)
from backend.app.modules.risk_management.geographic_exposure.services.service import (
    GeographicExposureService,
)
from backend.app.modules.risk_management.geographic_exposure.schemas import (
    GeographicExposureCalculateRequest,
)
from backend.app.modules.instrument_reference_data.instrument_master.models import (
    Instrument,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConcentrationAnalyticsService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ConcentrationRepository(session)
        self.instrument_exposure_service = InstrumentExposureService(session)
        self.sector_exposure_service = SectorExposureService(session)
        self.geographic_exposure_service = GeographicExposureService(session)
        self.multi_portfolio_service = MultiPortfolioService(session)

    async def calculate_concentration(
        self, req: ConcentrationCalculateRequest
    ) -> ConcentrationSummaryResponse:
        """
        Calculates concentration ratios and HHI metrics across the specified grouping dimension
        and exposure basis without duplicating upstream calculations.
        """
        # Step 1: Collect underlying grouped exposures
        grouped_exposures, unknown_exposure_amt, total_exp_coverage = await self._build_grouped_exposure_universe(req)

        # Step 2: Determine exposure magnitude based on exposure_basis
        # Returns list of dicts: {"group_id": ..., "group_key": ..., "group_name": ..., "long": ..., "short": ..., "net": ..., "gross": ..., "value": Decimal, "status": ...}
        evaluated_groups = []
        total_basis_exposure = Decimal("0.0")

        for g in grouped_exposures:
            l_val = g.get("long", Decimal("0.0"))
            s_val = g.get("short", Decimal("0.0"))
            n_val = g.get("net", Decimal("0.0"))
            g_val = g.get("gross", Decimal("0.0"))

            if req.exposure_basis == ConcentrationExposureBasis.GROSS_EXPOSURE:
                val = g_val
            elif req.exposure_basis == ConcentrationExposureBasis.LONG_EXPOSURE:
                val = l_val
            elif req.exposure_basis == ConcentrationExposureBasis.SHORT_EXPOSURE:
                val = s_val
            elif req.exposure_basis == ConcentrationExposureBasis.ABSOLUTE_NET_EXPOSURE:
                val = abs(n_val)
            else:
                val = g_val

            if val > Decimal("0.0"):
                evaluated_groups.append({
                    "group_id": g["group_id"],
                    "group_key": g["group_key"],
                    "group_name": g["group_name"],
                    "long": l_val,
                    "short": s_val,
                    "net": n_val,
                    "gross": g_val,
                    "value": val,
                    "classification_status": g.get("status", "CLASSIFIED"),
                    "source_ref": g.get("source_ref", None),
                })
                total_basis_exposure += val

        # Handle zero or empty exposure
        if total_basis_exposure == Decimal("0.0") or len(evaluated_groups) == 0:
            result = ConcentrationResult(
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                snapshot_id=req.snapshot_id,
                grouping_dimension=req.grouping_dimension,
                exposure_basis=req.exposure_basis,
                reporting_currency=req.reporting_currency,
                total_exposure=Decimal("0.0"),
                denominator_exposure=Decimal("0.0"),
                eligible_group_count=0,
                calculation_status=ConcentrationCalculationStatus.ZERO_EXPOSURE,
                calculated_at=utc_now(),
            )
            await self.repo.create_result(result)
            return ConcentrationSummaryResponse.model_validate(result)

        # Step 3: Sort descending by exposure value (deterministic tie-breaking on group_key)
        evaluated_groups.sort(key=lambda x: (-x["value"], x["group_key"]))

        # Step 4: Calculate individual and cumulative shares, HHI, and effective groups
        cumulative_share = Decimal("0.0")
        hhi_sum = Decimal("0.0")
        contributors_entities = []

        for rank_idx, item in enumerate(evaluated_groups, start=1):
            val = item["value"]
            share = (val / total_basis_exposure).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            cumulative_share += share
            if cumulative_share > Decimal("1.0"):
                cumulative_share = Decimal("1.000000")

            # HHI component: (w_i)^2
            hhi_sum += (share * share)

            contr = ConcentrationContributor(
                group_id=item["group_id"],
                group_key=item["group_key"],
                group_name=item["group_name"],
                grouping_dimension=req.grouping_dimension,
                rank=rank_idx,
                long_exposure=item["long"],
                short_exposure=item["short"],
                net_exposure=item["net"],
                gross_exposure=item["gross"],
                exposure_value=val,
                exposure_share=share,
                cumulative_share=cumulative_share.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP),
                source_exposure_reference=item["source_ref"],
                classification_status=item["classification_status"],
            )
            contributors_entities.append(contr)

        hhi_decimal = hhi_sum.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        hhi_10000 = (hhi_decimal * Decimal("10000")).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        if hhi_decimal > Decimal("0.0"):
            effective_groups = (Decimal("1.0") / hhi_decimal).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        else:
            effective_groups = Decimal("0.0")

        # Step 5: Concentration Ratios (CR1, CR3, CR5, CR10, CR20)
        def get_cr(k: int) -> Decimal:
            if not contributors_entities:
                return Decimal("0.0")
            limit_idx = min(k, len(contributors_entities))
            return contributors_entities[limit_idx - 1].cumulative_share

        cr1 = get_cr(1)
        cr3 = get_cr(3)
        cr5 = get_cr(5)
        cr10 = get_cr(10)
        cr20 = get_cr(20)

        # Coverage and unknown share
        unknown_share = Decimal("0.0")
        if total_basis_exposure > Decimal("0.0") and unknown_exposure_amt > Decimal("0.0"):
            unknown_share = (unknown_exposure_amt / (total_basis_exposure + unknown_exposure_amt)).quantize(
                Decimal("0.000001"), rounding=ROUND_HALF_UP
            )
        coverage = (Decimal("1.0") - unknown_share).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        calc_status = ConcentrationCalculationStatus.CALCULATED
        if len(evaluated_groups) < 5:
            calc_status = ConcentrationCalculationStatus.INSUFFICIENT_GROUPS

        result = ConcentrationResult(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            snapshot_id=req.snapshot_id,
            grouping_dimension=req.grouping_dimension,
            exposure_basis=req.exposure_basis,
            weighting_methodology="NORMALIZED_POSITIVE_SHARES",
            reporting_currency=req.reporting_currency,
            total_exposure=total_basis_exposure,
            denominator_exposure=total_basis_exposure,
            eligible_group_count=len(evaluated_groups),
            top_1_ratio=cr1,
            top_3_ratio=cr3,
            top_5_ratio=cr5,
            top_10_ratio=cr10,
            top_20_ratio=cr20,
            hhi_decimal=hhi_decimal,
            hhi_10000=hhi_10000,
            effective_number_of_groups=effective_groups,
            classification_coverage=coverage,
            unknown_exposure_share=unknown_share,
            calculation_status=calc_status,
            calculation_version="v1.0",
            calculated_at=utc_now(),
        )

        for c in contributors_entities:
            c.result_id = result.result_id
            result.contributors.append(c)

        await self.repo.create_result(result)

        # Step 6: Evaluate policy thresholds and flags
        policy = await self.repo.get_active_policy(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            grouping_dimension=req.grouping_dimension,
            exposure_basis=req.exposure_basis,
        )

        interp_level, flags = self._evaluate_policy(result, policy)

        resp = ConcentrationSummaryResponse.model_validate(result)
        resp.interpretation_level = interp_level
        resp.active_flags = flags
        resp.top_contributors = [
            ConcentrationContributorItemResponse.model_validate(c) for c in contributors_entities[:20]
        ]
        return resp

    async def compare_concentrations(
        self, current_result_id: str, prior_result_id: str
    ) -> ConcentrationComparisonResponse:
        """
        Compares concentration metrics between two calculation runs and classifies trends.
        """
        curr = await self.repo.get_result_by_id(current_result_id)
        prior = await self.repo.get_result_by_id(prior_result_id)

        if not curr or not prior:
            raise ValueError("Both calculation run results must exist to perform comparison.")

        # Check comparability
        comparable = True
        comp_status = "COMPARABLE"
        if curr.grouping_dimension != prior.grouping_dimension:
            comparable = False
            comp_status = "INCOMPATIBLE_GROUPING"
        elif curr.exposure_basis != prior.exposure_basis:
            comparable = False
            comp_status = "INCOMPATIBLE_EXPOSURE_BASIS"
        elif curr.reporting_currency != prior.reporting_currency:
            comparable = False
            comp_status = "INCOMPATIBLE_CURRENCY"

        hhi_dec_change = (curr.hhi_decimal - prior.hhi_decimal).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        hhi_10k_change = (curr.hhi_10000 - prior.hhi_10000).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        cr5_change = ((curr.top_5_ratio - prior.top_5_ratio) * Decimal("100.0")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        cr10_change = ((curr.top_10_ratio - prior.top_10_ratio) * Decimal("100.0")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )
        eff_change = (curr.effective_number_of_groups - prior.effective_number_of_groups).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )

        # Trend classification based on HHI 10k change
        if not comparable:
            trend = ConcentrationTrendStatus.INCOMPARABLE
        elif hhi_10k_change > Decimal("50.0"):
            trend = ConcentrationTrendStatus.INCREASING
        elif hhi_10k_change < Decimal("-50.0"):
            trend = ConcentrationTrendStatus.DECREASING
        else:
            trend = ConcentrationTrendStatus.STABLE

        comp = ConcentrationComparison(
            portfolio_id=curr.portfolio_id,
            portfolio_group_id=curr.portfolio_group_id,
            current_result_id=curr.result_id,
            prior_result_id=prior.result_id,
            grouping_dimension=curr.grouping_dimension,
            exposure_basis=curr.exposure_basis,
            weighting_methodology=curr.weighting_methodology,
            current_hhi_decimal=curr.hhi_decimal,
            prior_hhi_decimal=prior.hhi_decimal,
            hhi_decimal_change=hhi_dec_change,
            current_hhi_10000=curr.hhi_10000,
            prior_hhi_10000=prior.hhi_10000,
            hhi_10000_change=hhi_10k_change,
            current_cr5=curr.top_5_ratio,
            prior_cr5=prior.top_5_ratio,
            cr5_change_pp=cr5_change,
            current_cr10=curr.top_10_ratio,
            prior_cr10=prior.top_10_ratio,
            cr10_change_pp=cr10_change,
            current_effective_groups=curr.effective_number_of_groups,
            prior_effective_groups=prior.effective_number_of_groups,
            effective_groups_change=eff_change,
            trend_status=trend,
            comparability_status=comp_status,
            compared_at=utc_now(),
        )
        await self.repo.create_comparison(comp)
        return ConcentrationComparisonResponse.model_validate(comp)

    # -------------------------------------------------------------------------
    # Universe Builder & Aggregation Helpers
    # -------------------------------------------------------------------------

    async def _build_grouped_exposure_universe(
        self, req: ConcentrationCalculateRequest
    ) -> Tuple[List[Dict[str, Any]], Decimal, Decimal]:
        """
        Builds the exposure distribution for the specified dimension by consuming
        authoritative upstream M06.04 (Instrument), M06.03 (Sector/Industry),
        or M06.05 (Country/Region), and M04.01 for Issuer identity.
        """
        dim = req.grouping_dimension
        unknown_amt = Decimal("0.0")
        total_coverage = Decimal("1.0")

        # 1. INSTRUMENT & ISSUER: Consume M06.04
        if dim in (ConcentrationGroupingDimension.INSTRUMENT, ConcentrationGroupingDimension.ISSUER):
            inst_req = InstrumentExposureCalculateRequest(
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                as_of=req.as_of_date,
                reporting_currency=req.reporting_currency,
            )
            if req.portfolio_group_id:
                inst_res = await self.instrument_exposure_service.calculate_group_instrument_exposure(
                    req.portfolio_group_id, inst_req
                )
            else:
                inst_res = await self.instrument_exposure_service.calculate_portfolio_instrument_exposure(
                    req.portfolio_id or "", inst_req
                )

            if dim == ConcentrationGroupingDimension.INSTRUMENT:
                grouped = []
                for item in (inst_res.instruments or []):
                    name = item.instrument_name or item.symbol or item.instrument_id
                    grouped.append({
                        "group_id": item.instrument_id,
                        "group_key": item.instrument_id,
                        "group_name": name,
                        "long": item.long_market_value,
                        "short": item.short_market_value,
                        "net": item.net_market_value,
                        "gross": item.gross_market_value,
                        "status": "CLASSIFIED",
                        "source_ref": item.instrument_id,
                    })
                return grouped, Decimal("0.0"), Decimal("1.0")

            elif dim == ConcentrationGroupingDimension.ISSUER:
                # Group instruments by authoritative issuer_id / issuer_name from M04 Instrument Master
                issuer_map: Dict[str, Dict[str, Any]] = {}
                for item in (inst_res.instruments or []):
                    name = item.instrument_name or item.symbol or item.instrument_id
                    # Query instrument record to find issuer
                    stmt = select(Instrument).where(Instrument.instrument_id == item.instrument_id)
                    inst_rec = (await self.session.execute(stmt)).scalar_one_or_none()

                    issuer_key = inst_rec.issuer_name if (inst_rec and inst_rec.issuer_name) else f"ISSUER_{item.instrument_id}"
                    issuer_name = inst_rec.issuer_name if (inst_rec and inst_rec.issuer_name) else f"Issuer of {name}"

                    if issuer_key not in issuer_map:
                        issuer_map[issuer_key] = {
                            "group_id": issuer_key,
                            "group_key": issuer_key,
                            "group_name": issuer_name,
                            "long": Decimal("0.0"),
                            "short": Decimal("0.0"),
                            "net": Decimal("0.0"),
                            "gross": Decimal("0.0"),
                            "status": "CLASSIFIED" if (inst_rec and inst_rec.issuer_name) else "UNMAPPED_ISSUER",
                            "source_ref": f"ISSUER:{issuer_key}",
                        }

                    issuer_map[issuer_key]["long"] += item.long_market_value
                    issuer_map[issuer_key]["short"] += item.short_market_value
                    issuer_map[issuer_key]["net"] += item.net_market_value
                    issuer_map[issuer_key]["gross"] += item.gross_market_value

                return list(issuer_map.values()), Decimal("0.0"), Decimal("1.0")

        # 2. SECTOR & INDUSTRY: Consume M06.03
        elif dim in (ConcentrationGroupingDimension.SECTOR, ConcentrationGroupingDimension.INDUSTRY):
            sec_req = SectorExposureCalculateRequest(
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                as_of=req.as_of_date,
                reporting_currency=req.reporting_currency,
            )
            if req.portfolio_group_id:
                sec_res = await self.sector_exposure_service.calculate_group_sector_exposure(
                    req.portfolio_group_id, sec_req
                )
            else:
                sec_res = await self.sector_exposure_service.calculate_portfolio_sector_exposure(
                    req.portfolio_id or "", sec_req
                )

            grouped = []
            if dim == ConcentrationGroupingDimension.SECTOR:
                for item in sec_res.sectors:
                    grouped.append({
                        "group_id": item.sector_code,
                        "group_key": item.sector_code,
                        "group_name": item.sector_name,
                        "long": item.long_exposure,
                        "short": item.short_exposure,
                        "net": item.net_exposure,
                        "gross": item.gross_exposure,
                        "status": item.classification_status.value if hasattr(item.classification_status, "value") else str(item.classification_status),
                        "source_ref": f"SECTOR:{item.sector_code}",
                    })
            else:
                for item in sec_res.industries:
                    grouped.append({
                        "group_id": item.industry_code,
                        "group_key": item.industry_code,
                        "group_name": item.industry_name,
                        "long": item.long_exposure,
                        "short": item.short_exposure,
                        "net": item.net_exposure,
                        "gross": item.gross_exposure,
                        "status": item.classification_status.value if hasattr(item.classification_status, "value") else str(item.classification_status),
                        "source_ref": f"INDUSTRY:{item.industry_code}",
                    })

            for u in sec_res.unclassified:
                unknown_amt += u.gross_exposure
                # Retain unclassified in distribution explicitly
                grouped.append({
                    "group_id": f"UNCLASSIFIED_{u.instrument_id}",
                    "group_key": f"UNCLASSIFIED_{u.instrument_id}",
                    "group_name": f"Unclassified ({u.canonical_name})",
                    "long": u.long_exposure,
                    "short": u.short_exposure,
                    "net": u.net_exposure,
                    "gross": u.gross_exposure,
                    "status": "UNCLASSIFIED",
                    "source_ref": u.instrument_id,
                })

            return grouped, unknown_amt, Decimal("1.0")

        # 3. COUNTRY & REGION: Consume M06.05
        elif dim in (ConcentrationGroupingDimension.COUNTRY, ConcentrationGroupingDimension.REGION):
            geo_req = GeographicExposureCalculateRequest(
                portfolio_id=req.portfolio_id,
                portfolio_group_id=req.portfolio_group_id,
                as_of=req.as_of_date,
                reporting_currency=req.reporting_currency,
            )
            if req.portfolio_group_id:
                geo_res = await self.geographic_exposure_service.calculate_group_geographic_exposure(
                    req.portfolio_group_id, geo_req
                )
            else:
                geo_res = await self.geographic_exposure_service.calculate_portfolio_geographic_exposure(
                    req.portfolio_id or "", geo_req
                )

            grouped = []
            if dim == ConcentrationGroupingDimension.COUNTRY:
                for c in geo_res.countries:
                    grouped.append({
                        "group_id": c.country_iso3,
                        "group_key": c.country_iso3,
                        "group_name": c.country_name,
                        "long": c.long_exposure,
                        "short": c.short_exposure,
                        "net": c.net_exposure,
                        "gross": c.gross_exposure,
                        "status": "CLASSIFIED",
                        "source_ref": f"COUNTRY:{c.country_iso3}",
                    })
            else:
                for r in geo_res.regions:
                    grouped.append({
                        "group_id": r.region_code,
                        "group_key": r.region_code,
                        "group_name": r.region_name,
                        "long": r.long_exposure,
                        "short": r.short_exposure,
                        "net": r.net_exposure,
                        "gross": r.gross_exposure,
                        "status": "CLASSIFIED",
                        "source_ref": f"REGION:{r.region_code}",
                    })

            for u in geo_res.unknown_exposures:
                unknown_amt += u.gross_exposure
                grouped.append({
                    "group_id": f"UNKNOWN_GEO_{u.entity_id}",
                    "group_key": f"UNKNOWN_GEO_{u.entity_id}",
                    "group_name": f"Unknown Geo ({u.unknown_reason})",
                    "long": u.long_exposure,
                    "short": u.short_exposure,
                    "net": u.net_exposure,
                    "gross": u.gross_exposure,
                    "status": "UNKNOWN_GEOGRAPHY",
                    "source_ref": u.entity_id,
                })

            return grouped, unknown_amt, Decimal("1.0")

        return [], Decimal("0.0"), Decimal("1.0")

    def _evaluate_policy(
        self, result: ConcentrationResult, policy: Optional[ConcentrationPolicy]
    ) -> Tuple[ConcentrationInterpretationLevel, List[str]]:
        flags = []
        if not policy:
            # Default institutional checks
            if result.hhi_10000 >= Decimal("2500.0"):
                flags.append("HHI_CRITICAL_HIGH: HHI exceeds 2500.0")
                return ConcentrationInterpretationLevel.CRITICAL, flags
            elif result.hhi_10000 >= Decimal("1500.0"):
                flags.append("HHI_ELEVATED: HHI exceeds 1500.0")
                return ConcentrationInterpretationLevel.ELEVATED, flags
            elif result.top_1_ratio >= Decimal("0.25"):
                flags.append("TOP_1_ELEVATED: Single group accounts for >= 25% of exposure")
                return ConcentrationInterpretationLevel.ELEVATED, flags
            return ConcentrationInterpretationLevel.NORMAL, flags

        # Configured policy checks
        level = ConcentrationInterpretationLevel.NORMAL

        if result.top_1_ratio >= policy.top_1_critical:
            flags.append(f"TOP_1_CRITICAL: Top-1 share {result.top_1_ratio} exceeds critical {policy.top_1_critical}")
            level = ConcentrationInterpretationLevel.CRITICAL
        elif result.top_1_ratio >= policy.top_1_warning:
            flags.append(f"TOP_1_WARNING: Top-1 share {result.top_1_ratio} exceeds warning {policy.top_1_warning}")
            if level != ConcentrationInterpretationLevel.CRITICAL:
                level = ConcentrationInterpretationLevel.ELEVATED

        if result.top_5_ratio >= policy.cr5_critical:
            flags.append(f"CR5_CRITICAL: CR5 {result.top_5_ratio} exceeds critical {policy.cr5_critical}")
            level = ConcentrationInterpretationLevel.CRITICAL
        elif result.top_5_ratio >= policy.cr5_warning:
            flags.append(f"CR5_WARNING: CR5 {result.top_5_ratio} exceeds warning {policy.cr5_warning}")
            if level != ConcentrationInterpretationLevel.CRITICAL:
                level = ConcentrationInterpretationLevel.ELEVATED

        if result.hhi_10000 >= policy.hhi_10000_critical:
            flags.append(f"HHI_CRITICAL: HHI 10k {result.hhi_10000} exceeds critical {policy.hhi_10000_critical}")
            level = ConcentrationInterpretationLevel.CRITICAL
        elif result.hhi_10000 >= policy.hhi_10000_warning:
            flags.append(f"HHI_WARNING: HHI 10k {result.hhi_10000} exceeds warning {policy.hhi_10000_warning}")
            if level != ConcentrationInterpretationLevel.CRITICAL:
                level = ConcentrationInterpretationLevel.ELEVATED

        if result.effective_number_of_groups <= policy.min_effective_groups_critical:
            flags.append(f"EFF_GROUPS_CRITICAL: Effective groups {result.effective_number_of_groups} <= critical {policy.min_effective_groups_critical}")
            level = ConcentrationInterpretationLevel.CRITICAL
        elif result.effective_number_of_groups <= policy.min_effective_groups_warning:
            flags.append(f"EFF_GROUPS_WARNING: Effective groups {result.effective_number_of_groups} <= warning {policy.min_effective_groups_warning}")
            if level != ConcentrationInterpretationLevel.CRITICAL:
                level = ConcentrationInterpretationLevel.ELEVATED

        return level, flags

    # Policy API
    async def create_policy(self, req: ConcentrationPolicyCreateRequest) -> ConcentrationPolicyResponse:
        pol = ConcentrationPolicy(
            portfolio_id=req.portfolio_id,
            portfolio_group_id=req.portfolio_group_id,
            grouping_dimension=req.grouping_dimension,
            exposure_basis=req.exposure_basis,
            top_1_warning=req.top_1_warning,
            top_1_critical=req.top_1_critical,
            cr5_warning=req.cr5_warning,
            cr5_critical=req.cr5_critical,
            hhi_10000_warning=req.hhi_10000_warning,
            hhi_10000_critical=req.hhi_10000_critical,
            min_effective_groups_warning=req.min_effective_groups_warning,
            min_effective_groups_critical=req.min_effective_groups_critical,
            interpretation_policy=req.interpretation_policy,
            policy_version=req.policy_version,
            effective_from=utc_now(),
        )
        await self.repo.create_policy(pol)
        return ConcentrationPolicyResponse.model_validate(pol)
