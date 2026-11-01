"""
M06.05 Geographic Exposure Service.
Core engine for aggregating exposures by country and region using configurable attribution modes
(ISSUER_DOMICILE, REVENUE_GEOGRAPHY), calculating dual weights, tracking unknown geographies,
and performing historical snapshot comparisons.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.modules.instrument_reference_data.geographic_classification.models import (
    GeographicAttributeType,
    GeographicMappingStatus,
)
from backend.app.modules.instrument_reference_data.geographic_classification.repositories.repository import (
    GeographicReferenceRepository,
)
from backend.app.modules.risk_management.geographic_exposure.models import (
    GeographicExposureCalculationRun,
    CountryExposureResult,
    RegionExposureResult,
    UnknownGeographicExposure,
    GeographicExposureComparison,
    GeographicLevel,
    GeographicCoverageStatus,
)
from backend.app.modules.risk_management.geographic_exposure.schemas import (
    GeographicExposureCalculateRequest,
    GeographicExposureSummaryResponse,
    CountryExposureItemResponse,
    RegionExposureItemResponse,
    UnknownGeographicItemResponse,
    GeographicComparisonResponse,
    GeographicComparisonItemResponse,
)
from backend.app.modules.risk_management.geographic_exposure.repositories.repository import (
    GeographicExposureRepository,
)
from backend.app.modules.risk_management.instrument_exposure.services.service import (
    InstrumentExposureService,
)
from backend.app.modules.risk_management.instrument_exposure.schemas import (
    InstrumentExposureCalculateRequest,
)
from backend.app.modules.portfolio_management.portfolio_history.repositories.repository import (
    PortfolioHistoryRepository,
)
from backend.app.modules.portfolio_management.multi_portfolio_management.services.service import (
    MultiPortfolioService,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class GeographicExposureService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = GeographicExposureRepository(session)
        self.geo_ref_repo = GeographicReferenceRepository(session)
        self.inst_exp_svc = InstrumentExposureService(session)
        self.hist_repo = PortfolioHistoryRepository(session)
        self.multi_port_svc = MultiPortfolioService(session)

    async def calculate_portfolio_geographic_exposure(
        self, portfolio_id: str, request: GeographicExposureCalculateRequest
    ) -> GeographicExposureSummaryResponse:
        now = utc_now()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"
        attr_mode = request.geographic_attribute or GeographicAttributeType.ISSUER_DOMICILE
        tax_scheme = request.taxonomy_scheme_code or "STANDARD"

        # 1. Fetch authoritative instrument exposure from M06.04
        inst_summary = await self.inst_exp_svc.calculate_portfolio_instrument_exposure(
            portfolio_id,
            InstrumentExposureCalculateRequest(
                portfolio_id=portfolio_id,
                as_of=as_of,
                knowledge_as_of=know_as_of,
                reporting_currency=rep_curr,
            ),
        )

        nav = inst_summary.nav
        tot_long = inst_summary.total_long_exposure
        tot_short = inst_summary.total_short_exposure
        tot_gross = inst_summary.total_gross_exposure
        tot_net = inst_summary.total_net_exposure

        # 2. Accumulators
        country_aggs: Dict[str, Dict[str, Any]] = {}
        region_aggs: Dict[str, Dict[str, Any]] = {}
        unknown_list: List[UnknownGeographicExposure] = []

        run_id = f"GEO-RUN-{uuid.uuid4().hex[:12].upper()}"
        classified_gross = Decimal("0.000000")
        unknown_gross = Decimal("0.000000")

        # 3. Attribute each instrument
        for inst in inst_summary.instruments:
            i_id = inst.instrument_id
            i_long = inst.long_market_value
            i_short = inst.short_market_value
            i_gross = inst.gross_market_value
            i_net = inst.net_market_value

            if attr_mode == GeographicAttributeType.REVENUE_GEOGRAPHY:
                # Revenue geography attribution
                revs = await self.geo_ref_repo.get_revenue_geography(i_id)
                if not revs:
                    # Mark as unknown revenue geography
                    unknown_gross += i_gross
                    unknown_list.append(
                        UnknownGeographicExposure(
                            run_id=run_id,
                            instrument_id=i_id,
                            reason_code="UNKNOWN_REVENUE_GEOGRAPHY",
                            unmapped_gross_exposure=i_gross,
                            unmapped_weight=(i_gross / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else Decimal("0.000000"),
                        )
                    )
                    continue

                total_alloc = sum((r.allocation_weight for r in revs), Decimal("0.000000"))
                for r in revs:
                    alloc = r.allocation_weight
                    c_id = r.country_id
                    reg_id = r.region_id

                    part_long = i_long * alloc
                    part_short = i_short * alloc
                    part_gross = i_gross * alloc
                    part_net = i_net * alloc
                    classified_gross += part_gross

                    if c_id:
                        if c_id not in country_aggs:
                            c_meta = await self.geo_ref_repo.get_country(c_id)
                            reg_meta = await self.geo_ref_repo.get_country_region(c_id, tax_scheme)
                            country_aggs[c_id] = {
                                "country_id": c_id,
                                "country_name": c_meta.canonical_name if c_meta else c_id,
                                "iso_alpha2": c_meta.iso_alpha2 if c_meta else c_id[:2],
                                "region_id": reg_meta.region_id if reg_meta else "UNKNOWN_REGION",
                                "region_name": reg_meta.region_name if reg_meta else "Unknown Region",
                                "long": Decimal("0.000000"),
                                "short": Decimal("0.000000"),
                                "net": Decimal("0.000000"),
                                "gross": Decimal("0.000000"),
                                "instruments": set(),
                            }
                        country_aggs[c_id]["long"] += part_long
                        country_aggs[c_id]["short"] += part_short
                        country_aggs[c_id]["gross"] += part_gross
                        country_aggs[c_id]["net"] += part_net
                        country_aggs[c_id]["instruments"].add(i_id)

                        # Roll up to region
                        r_key = country_aggs[c_id]["region_id"]
                        if r_key not in region_aggs:
                            region_aggs[r_key] = {
                                "region_id": r_key,
                                "region_code": r_key,
                                "region_name": country_aggs[c_id]["region_name"],
                                "long": Decimal("0.000000"),
                                "short": Decimal("0.000000"),
                                "net": Decimal("0.000000"),
                                "gross": Decimal("0.000000"),
                                "instruments": set(),
                            }
                        region_aggs[r_key]["long"] += part_long
                        region_aggs[r_key]["short"] += part_short
                        region_aggs[r_key]["gross"] += part_gross
                        region_aggs[r_key]["net"] += part_net
                        region_aggs[r_key]["instruments"].add(i_id)

                if total_alloc < Decimal("1.000000"):
                    # Residual unknown
                    residual_alloc = Decimal("1.000000") - total_alloc
                    res_gross = i_gross * residual_alloc
                    unknown_gross += res_gross
                    unknown_list.append(
                        UnknownGeographicExposure(
                            run_id=run_id,
                            instrument_id=i_id,
                            reason_code="PARTIAL_REVENUE_GEOGRAPHY_RESIDUAL",
                            unmapped_gross_exposure=res_gross,
                            unmapped_weight=(res_gross / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else Decimal("0.000000"),
                        )
                    )

            else:
                # Domicile / Headquarters attribution
                assigns = await self.geo_ref_repo.get_issuer_geography(i_id, attr_mode.value)
                if not assigns:
                    unknown_gross += i_gross
                    unknown_list.append(
                        UnknownGeographicExposure(
                            run_id=run_id,
                            instrument_id=i_id,
                            reason_code="UNMAPPED_DOMICILE",
                            unmapped_gross_exposure=i_gross,
                            unmapped_weight=(i_gross / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else Decimal("0.000000"),
                        )
                    )
                    continue

                for a in assigns:
                    c_id = a.country_id
                    alloc = a.allocation_weight
                    part_long = i_long * alloc
                    part_short = i_short * alloc
                    part_gross = i_gross * alloc
                    part_net = i_net * alloc
                    classified_gross += part_gross

                    if c_id not in country_aggs:
                        c_meta = await self.geo_ref_repo.get_country(c_id)
                        reg_meta = await self.geo_ref_repo.get_country_region(c_id, tax_scheme)
                        country_aggs[c_id] = {
                            "country_id": c_id,
                            "country_name": c_meta.canonical_name if c_meta else c_id,
                            "iso_alpha2": c_meta.iso_alpha2 if c_meta else c_id[:2],
                            "region_id": reg_meta.region_id if reg_meta else "UNKNOWN_REGION",
                            "region_name": reg_meta.region_name if reg_meta else "Unknown Region",
                            "long": Decimal("0.000000"),
                            "short": Decimal("0.000000"),
                            "net": Decimal("0.000000"),
                            "gross": Decimal("0.000000"),
                            "instruments": set(),
                        }
                    country_aggs[c_id]["long"] += part_long
                    country_aggs[c_id]["short"] += part_short
                    country_aggs[c_id]["gross"] += part_gross
                    country_aggs[c_id]["net"] += part_net
                    country_aggs[c_id]["instruments"].add(i_id)

                    r_key = country_aggs[c_id]["region_id"]
                    if r_key not in region_aggs:
                        region_aggs[r_key] = {
                            "region_id": r_key,
                            "region_code": r_key,
                            "region_name": country_aggs[c_id]["region_name"],
                            "long": Decimal("0.000000"),
                            "short": Decimal("0.000000"),
                            "net": Decimal("0.000000"),
                            "gross": Decimal("0.000000"),
                            "instruments": set(),
                        }
                    region_aggs[r_key]["long"] += part_long
                    region_aggs[r_key]["short"] += part_short
                    region_aggs[r_key]["gross"] += part_gross
                    region_aggs[r_key]["net"] += part_net
                    region_aggs[r_key]["instruments"].add(i_id)

        # Coverage ratio
        cov_ratio = (
            (classified_gross / tot_gross).quantize(Decimal("0.000001"))
            if tot_gross > Decimal("0.0")
            else Decimal("1.000000")
        )
        if cov_ratio == Decimal("1.000000"):
            cov_status = GeographicCoverageStatus.COMPLETE.value
        elif cov_ratio >= Decimal("0.800000"):
            cov_status = GeographicCoverageStatus.PARTIAL.value
        else:
            cov_status = GeographicCoverageStatus.CRITICAL_GAP.value

        # Build country results
        country_results: List[CountryExposureResult] = []
        for c_id, d in country_aggs.items():
            l_val = d["long"]
            s_val = d["short"]
            g_val = d["gross"]
            n_val = d["net"]

            l_nav = (l_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            s_nav = (s_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            g_nav = (g_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            n_nav = (n_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            g_contrib = (g_val / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else None

            country_results.append(
                CountryExposureResult(
                    run_id=run_id,
                    country_id=c_id,
                    country_name=d["country_name"],
                    iso_alpha2=d["iso_alpha2"],
                    region_id=d["region_id"],
                    region_name=d["region_name"],
                    long_exposure=l_val,
                    short_exposure=s_val,
                    net_exposure=n_val,
                    gross_exposure=g_val,
                    long_nav_weight=l_nav,
                    short_nav_weight=s_nav,
                    net_nav_weight=n_nav,
                    gross_nav_weight=g_nav,
                    gross_contribution_weight=g_contrib,
                    instrument_count=len(d["instruments"]),
                )
            )

        # Sort and rank countries by gross exposure
        country_results.sort(key=lambda x: (x.gross_exposure, x.country_id), reverse=True)
        for idx, item in enumerate(country_results, start=1):
            item.rank = idx

        # Build region results
        region_results: List[RegionExposureResult] = []
        for r_id, d in region_aggs.items():
            l_val = d["long"]
            s_val = d["short"]
            g_val = d["gross"]
            n_val = d["net"]

            l_nav = (l_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            s_nav = (s_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            g_nav = (g_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            n_nav = (n_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None
            g_contrib = (g_val / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else None

            region_results.append(
                RegionExposureResult(
                    run_id=run_id,
                    region_id=r_id,
                    region_code=d["region_code"],
                    region_name=d["region_name"],
                    taxonomy_scheme_code=tax_scheme,
                    hierarchy_level=1,
                    long_exposure=l_val,
                    short_exposure=s_val,
                    net_exposure=n_val,
                    gross_exposure=g_val,
                    long_nav_weight=l_nav,
                    short_nav_weight=s_nav,
                    net_nav_weight=n_nav,
                    gross_nav_weight=g_nav,
                    gross_contribution_weight=g_contrib,
                    instrument_count=len(d["instruments"]),
                )
            )

        region_results.sort(key=lambda x: (x.gross_exposure, x.region_id), reverse=True)
        for idx, item in enumerate(region_results, start=1):
            item.rank = idx

        dominant_country = country_results[0].country_id if country_results else None
        dominant_region = region_results[0].region_id if region_results else None

        run = GeographicExposureCalculationRun(
            run_id=run_id,
            portfolio_id=portfolio_id,
            entity_type="PORTFOLIO",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            geographic_attribute=attr_mode.value,
            taxonomy_scheme_code=tax_scheme,
            nav=nav,
            total_long_exposure=tot_long,
            total_short_exposure=tot_short,
            total_net_exposure=tot_net,
            total_gross_exposure=tot_gross,
            classified_gross_exposure=classified_gross,
            unknown_gross_exposure=unknown_gross,
            coverage_ratio=cov_ratio,
            coverage_status=cov_status,
            dominant_country_id=dominant_country,
            dominant_region_id=dominant_region,
            calculated_at=now,
        )

        await self.repo.save_calculation_run(run, country_results, region_results, unknown_list)

        return GeographicExposureSummaryResponse(
            run_id=run.run_id,
            portfolio_id=portfolio_id,
            entity_type="PORTFOLIO",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            reporting_currency=rep_curr,
            geographic_attribute=attr_mode.value,
            taxonomy_scheme_code=tax_scheme,
            nav=nav,
            total_long_exposure=tot_long,
            total_short_exposure=tot_short,
            total_net_exposure=tot_net,
            total_gross_exposure=tot_gross,
            classified_gross_exposure=classified_gross,
            unknown_gross_exposure=unknown_gross,
            coverage_ratio=cov_ratio,
            coverage_status=cov_status,
            dominant_country_id=dominant_country,
            dominant_region_id=dominant_region,
            countries=[
                CountryExposureItemResponse(
                    country_id=c.country_id,
                    country_name=c.country_name,
                    iso_alpha2=c.iso_alpha2,
                    region_id=c.region_id,
                    region_name=c.region_name,
                    long_exposure=c.long_exposure,
                    short_exposure=c.short_exposure,
                    net_exposure=c.net_exposure,
                    gross_exposure=c.gross_exposure,
                    long_nav_weight=c.long_nav_weight,
                    short_nav_weight=c.short_nav_weight,
                    net_nav_weight=c.net_nav_weight,
                    gross_nav_weight=c.gross_nav_weight,
                    gross_contribution_weight=c.gross_contribution_weight,
                    instrument_count=c.instrument_count,
                    rank=c.rank,
                )
                for c in country_results
            ],
            regions=[
                RegionExposureItemResponse(
                    region_id=r.region_id,
                    region_code=r.region_code,
                    region_name=r.region_name,
                    taxonomy_scheme_code=r.taxonomy_scheme_code,
                    hierarchy_level=r.hierarchy_level,
                    long_exposure=r.long_exposure,
                    short_exposure=r.short_exposure,
                    net_exposure=r.net_exposure,
                    gross_exposure=r.gross_exposure,
                    long_nav_weight=r.long_nav_weight,
                    short_nav_weight=r.short_nav_weight,
                    net_nav_weight=r.net_nav_weight,
                    gross_nav_weight=r.gross_nav_weight,
                    gross_contribution_weight=r.gross_contribution_weight,
                    instrument_count=r.instrument_count,
                    rank=r.rank,
                )
                for r in region_results
            ],
            unknown_holdings=[
                UnknownGeographicItemResponse(
                    instrument_id=u.instrument_id,
                    reason_code=u.reason_code,
                    unmapped_gross_exposure=u.unmapped_gross_exposure,
                    unmapped_weight=u.unmapped_weight,
                )
                for u in unknown_list
            ],
        )

    async def calculate_group_geographic_exposure(
        self, group_id: str, request: GeographicExposureCalculateRequest
    ) -> GeographicExposureSummaryResponse:
        """
        Consolidates geographic exposures across member portfolios in a portfolio group
        using M05.08 group resolution.
        """
        now = utc_now()
        as_of = request.as_of or now
        know_as_of = request.knowledge_as_of or now
        rep_curr = request.reporting_currency or "USD"
        attr_mode = request.geographic_attribute or GeographicAttributeType.ISSUER_DOMICILE
        tax_scheme = request.taxonomy_scheme_code or "STANDARD"

        inst_summary = await self.inst_exp_svc.calculate_group_instrument_exposure(
            group_id,
            InstrumentExposureCalculateRequest(
                portfolio_group_id=group_id,
                as_of=as_of,
                knowledge_as_of=know_as_of,
                reporting_currency=rep_curr,
            ),
        )

        nav = inst_summary.nav
        tot_long = inst_summary.total_long_exposure
        tot_short = inst_summary.total_short_exposure
        tot_gross = inst_summary.total_gross_exposure
        tot_net = inst_summary.total_net_exposure

        country_aggs: Dict[str, Dict[str, Any]] = {}
        region_aggs: Dict[str, Dict[str, Any]] = {}
        unknown_list: List[UnknownGeographicExposure] = []

        run_id = f"GEO-RUN-{uuid.uuid4().hex[:12].upper()}"
        classified_gross = Decimal("0.000000")
        unknown_gross = Decimal("0.000000")

        for inst in inst_summary.instruments:
            i_id = inst.instrument_id
            i_long = inst.long_market_value
            i_short = inst.short_market_value
            i_gross = inst.gross_market_value
            i_net = inst.net_market_value

            assigns = await self.geo_ref_repo.get_issuer_geography(i_id, attr_mode.value)
            if not assigns:
                unknown_gross += i_gross
                unknown_list.append(
                    UnknownGeographicExposure(
                        run_id=run_id,
                        instrument_id=i_id,
                        reason_code="UNMAPPED_DOMICILE",
                        unmapped_gross_exposure=i_gross,
                        unmapped_weight=(i_gross / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else Decimal("0.000000"),
                    )
                )
                continue

            for a in assigns:
                c_id = a.country_id
                alloc = a.allocation_weight
                part_long = i_long * alloc
                part_short = i_short * alloc
                part_gross = i_gross * alloc
                part_net = i_net * alloc
                classified_gross += part_gross

                if c_id not in country_aggs:
                    c_meta = await self.geo_ref_repo.get_country(c_id)
                    reg_meta = await self.geo_ref_repo.get_country_region(c_id, tax_scheme)
                    country_aggs[c_id] = {
                        "country_id": c_id,
                        "country_name": c_meta.canonical_name if c_meta else c_id,
                        "iso_alpha2": c_meta.iso_alpha2 if c_meta else c_id[:2],
                        "region_id": reg_meta.region_id if reg_meta else "UNKNOWN_REGION",
                        "region_name": reg_meta.region_name if reg_meta else "Unknown Region",
                        "long": Decimal("0.000000"),
                        "short": Decimal("0.000000"),
                        "net": Decimal("0.000000"),
                        "gross": Decimal("0.000000"),
                        "instruments": set(),
                    }
                country_aggs[c_id]["long"] += part_long
                country_aggs[c_id]["short"] += part_short
                country_aggs[c_id]["gross"] += part_gross
                country_aggs[c_id]["net"] += part_net
                country_aggs[c_id]["instruments"].add(i_id)

                r_key = country_aggs[c_id]["region_id"]
                if r_key not in region_aggs:
                    region_aggs[r_key] = {
                        "region_id": r_key,
                        "region_code": r_key,
                        "region_name": country_aggs[c_id]["region_name"],
                        "long": Decimal("0.000000"),
                        "short": Decimal("0.000000"),
                        "net": Decimal("0.000000"),
                        "gross": Decimal("0.000000"),
                        "instruments": set(),
                    }
                region_aggs[r_key]["long"] += part_long
                region_aggs[r_key]["short"] += part_short
                region_aggs[r_key]["gross"] += part_gross
                region_aggs[r_key]["net"] += part_net
                region_aggs[r_key]["instruments"].add(i_id)

        cov_ratio = (
            (classified_gross / tot_gross).quantize(Decimal("0.000001"))
            if tot_gross > Decimal("0.0")
            else Decimal("1.000000")
        )
        cov_status = GeographicCoverageStatus.COMPLETE.value if cov_ratio == Decimal("1.000000") else GeographicCoverageStatus.PARTIAL.value

        country_results: List[CountryExposureResult] = []
        for c_id, d in country_aggs.items():
            g_val = d["gross"]
            country_results.append(
                CountryExposureResult(
                    run_id=run_id,
                    country_id=c_id,
                    country_name=d["country_name"],
                    iso_alpha2=d["iso_alpha2"],
                    region_id=d["region_id"],
                    region_name=d["region_name"],
                    long_exposure=d["long"],
                    short_exposure=d["short"],
                    net_exposure=d["net"],
                    gross_exposure=g_val,
                    long_nav_weight=(d["long"] / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    short_nav_weight=(d["short"] / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    net_nav_weight=(d["net"] / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    gross_nav_weight=(g_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    gross_contribution_weight=(g_val / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else None,
                    instrument_count=len(d["instruments"]),
                )
            )
        country_results.sort(key=lambda x: (x.gross_exposure, x.country_id), reverse=True)
        for idx, item in enumerate(country_results, start=1):
            item.rank = idx

        region_results: List[RegionExposureResult] = []
        for r_id, d in region_aggs.items():
            g_val = d["gross"]
            region_results.append(
                RegionExposureResult(
                    run_id=run_id,
                    region_id=r_id,
                    region_code=d["region_code"],
                    region_name=d["region_name"],
                    taxonomy_scheme_code=tax_scheme,
                    hierarchy_level=1,
                    long_exposure=d["long"],
                    short_exposure=d["short"],
                    net_exposure=d["net"],
                    gross_exposure=g_val,
                    long_nav_weight=(d["long"] / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    short_nav_weight=(d["short"] / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    net_nav_weight=(d["net"] / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    gross_nav_weight=(g_val / nav).quantize(Decimal("0.000001")) if nav > Decimal("0.0") else None,
                    gross_contribution_weight=(g_val / tot_gross).quantize(Decimal("0.000001")) if tot_gross > Decimal("0.0") else None,
                    instrument_count=len(d["instruments"]),
                )
            )
        region_results.sort(key=lambda x: (x.gross_exposure, x.region_id), reverse=True)
        for idx, item in enumerate(region_results, start=1):
            item.rank = idx

        run = GeographicExposureCalculationRun(
            run_id=run_id,
            portfolio_id=group_id,
            portfolio_group_id=group_id,
            entity_type="PORTFOLIO_GROUP",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            knowledge_as_of=know_as_of,
            reporting_currency=rep_curr,
            geographic_attribute=attr_mode.value,
            taxonomy_scheme_code=tax_scheme,
            nav=nav,
            total_long_exposure=tot_long,
            total_short_exposure=tot_short,
            total_net_exposure=tot_net,
            total_gross_exposure=tot_gross,
            classified_gross_exposure=classified_gross,
            unknown_gross_exposure=unknown_gross,
            coverage_ratio=cov_ratio,
            coverage_status=cov_status,
            dominant_country_id=country_results[0].country_id if country_results else None,
            dominant_region_id=region_results[0].region_id if region_results else None,
            calculated_at=now,
        )

        await self.repo.save_calculation_run(run, country_results, region_results, unknown_list)

        return GeographicExposureSummaryResponse(
            run_id=run.run_id,
            portfolio_id=group_id,
            portfolio_group_id=group_id,
            entity_type="PORTFOLIO_GROUP",
            snapshot_id=request.snapshot_id,
            as_of=as_of,
            reporting_currency=rep_curr,
            geographic_attribute=attr_mode.value,
            taxonomy_scheme_code=tax_scheme,
            nav=nav,
            total_long_exposure=tot_long,
            total_short_exposure=tot_short,
            total_net_exposure=tot_net,
            total_gross_exposure=tot_gross,
            classified_gross_exposure=classified_gross,
            unknown_gross_exposure=unknown_gross,
            coverage_ratio=cov_ratio,
            coverage_status=cov_status,
            dominant_country_id=run.dominant_country_id,
            dominant_region_id=run.dominant_region_id,
            countries=[
                CountryExposureItemResponse(
                    country_id=c.country_id,
                    country_name=c.country_name,
                    iso_alpha2=c.iso_alpha2,
                    region_id=c.region_id,
                    region_name=c.region_name,
                    long_exposure=c.long_exposure,
                    short_exposure=c.short_exposure,
                    net_exposure=c.net_exposure,
                    gross_exposure=c.gross_exposure,
                    long_nav_weight=c.long_nav_weight,
                    short_nav_weight=c.short_nav_weight,
                    net_nav_weight=c.net_nav_weight,
                    gross_nav_weight=c.gross_nav_weight,
                    gross_contribution_weight=c.gross_contribution_weight,
                    instrument_count=c.instrument_count,
                    rank=c.rank,
                )
                for c in country_results
            ],
            regions=[
                RegionExposureItemResponse(
                    region_id=r.region_id,
                    region_code=r.region_code,
                    region_name=r.region_name,
                    taxonomy_scheme_code=r.taxonomy_scheme_code,
                    hierarchy_level=r.hierarchy_level,
                    long_exposure=r.long_exposure,
                    short_exposure=r.short_exposure,
                    net_exposure=r.net_exposure,
                    gross_exposure=r.gross_exposure,
                    long_nav_weight=r.long_nav_weight,
                    short_nav_weight=r.short_nav_weight,
                    net_nav_weight=r.net_nav_weight,
                    gross_nav_weight=r.gross_nav_weight,
                    gross_contribution_weight=r.gross_contribution_weight,
                    instrument_count=r.instrument_count,
                    rank=r.rank,
                )
                for r in region_results
            ],
            unknown_holdings=[
                UnknownGeographicItemResponse(
                    instrument_id=u.instrument_id,
                    reason_code=u.reason_code,
                    unmapped_gross_exposure=u.unmapped_gross_exposure,
                    unmapped_weight=u.unmapped_weight,
                )
                for u in unknown_list
            ],
        )

    async def compare_snapshots(
        self,
        portfolio_id: str,
        current_snapshot_id: str,
        prior_snapshot_id: str,
        geographic_level: GeographicLevel = GeographicLevel.COUNTRY,
    ) -> GeographicComparisonResponse:
        """
        Compares country or regional geographic exposure between two historical snapshots from M05.07.
        """
        curr_positions = await self.hist_repo.get_snapshot_positions(current_snapshot_id)
        prior_positions = await self.hist_repo.get_snapshot_positions(prior_snapshot_id)
        curr_vals = await self.hist_repo.get_snapshot_valuations(current_snapshot_id)
        prior_vals = await self.hist_repo.get_snapshot_valuations(prior_snapshot_id)

        curr_val_map = {v.instrument_id: v for v in curr_vals}
        prior_val_map = {v.instrument_id: v for v in prior_vals}

        async def aggregate_snapshot_geo(positions, val_map):
            geo_aggs: Dict[str, Dict[str, Any]] = {}
            for p in positions:
                i_id = p.instrument_id
                v = val_map.get(i_id)
                px = v.market_price if v else Decimal("1.000000")
                qty = p.net_signed_quantity
                mv = abs(qty) * px

                assigns = await self.geo_ref_repo.get_issuer_geography(i_id)
                c_id = assigns[0].country_id if assigns else "UNKNOWN"

                if geographic_level == GeographicLevel.REGION:
                    reg = await self.geo_ref_repo.get_country_region(c_id)
                    key = reg.region_id if reg else "UNKNOWN_REGION"
                    name = reg.region_name if reg else "Unknown Region"
                else:
                    key = c_id
                    c_meta = await self.geo_ref_repo.get_country(c_id)
                    name = c_meta.canonical_name if c_meta else c_id

                if key not in geo_aggs:
                    geo_aggs[key] = {"name": name, "gross": Decimal("0.000000")}
                geo_aggs[key]["gross"] += mv
            return geo_aggs

        curr_geo = await aggregate_snapshot_geo(curr_positions, curr_val_map)
        prior_geo = await aggregate_snapshot_geo(prior_positions, prior_val_map)

        all_keys = set(curr_geo.keys()).union(set(prior_geo.keys()))
        comparisons: List[GeographicExposureComparison] = []
        items_resp: List[GeographicComparisonItemResponse] = []
        now = utc_now()

        for k in all_keys:
            c_g = curr_geo.get(k, {}).get("gross", Decimal("0.000000"))
            p_g = prior_geo.get(k, {}).get("gross", Decimal("0.000000"))
            name = curr_geo.get(k, {}).get("name") or prior_geo.get(k, {}).get("name") or k
            diff_g = c_g - p_g

            pct_change: Optional[Decimal] = None
            if p_g > Decimal("0.0"):
                pct_change = ((c_g - p_g) / p_g * Decimal("100.0")).quantize(Decimal("0.000001"))

            lifecycle = "UNCHANGED"
            if p_g == Decimal("0.0") and c_g > Decimal("0.0"):
                lifecycle = "NEW_GEOGRAPHIC_EXPOSURE"
            elif p_g > Decimal("0.0") and c_g == Decimal("0.0"):
                lifecycle = "REMOVED_GEOGRAPHIC_EXPOSURE"
            elif c_g > p_g:
                lifecycle = "INCREASED_EXPOSURE"
            elif c_g < p_g:
                lifecycle = "REDUCED_EXPOSURE"

            comp = GeographicExposureComparison(
                portfolio_id=portfolio_id,
                current_snapshot_id=current_snapshot_id,
                prior_snapshot_id=prior_snapshot_id,
                geographic_level=geographic_level.value,
                entity_id=k,
                entity_name=name,
                current_gross_exposure=c_g,
                prior_gross_exposure=p_g,
                gross_exposure_change=diff_g,
                gross_percentage_change=pct_change,
                lifecycle_status=lifecycle,
                calculated_at=now,
            )
            comparisons.append(comp)

            items_resp.append(
                GeographicComparisonItemResponse(
                    entity_id=k,
                    entity_name=name,
                    current_gross_exposure=c_g,
                    prior_gross_exposure=p_g,
                    gross_exposure_change=diff_g,
                    gross_percentage_change=pct_change,
                    lifecycle_status=lifecycle,
                )
            )

        await self.repo.save_comparisons(comparisons)

        return GeographicComparisonResponse(
            portfolio_id=portfolio_id,
            current_snapshot_id=current_snapshot_id,
            prior_snapshot_id=prior_snapshot_id,
            geographic_level=geographic_level.value,
            items=items_resp,
        )
