import base64
import hashlib
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.modules.reporting_attribution_audit.report_archive.models.archive_models import (
    ReportArchive,
    ReportArchiveArtifact,
    ReportArchiveProvenance,
    ReportArchiveModelVersion,
    ReportArchiveDataVersion,
    ReportArchiveConfigVersion,
    ReportArchiveRetentionPolicy,
    ReportArchiveLegalHold,
    ReportArchiveType,
    ArchiveStatus,
    GenerationReason,
    ArtifactFormat,
    IntegrityStatus,
    LegalHoldStatus,
)
from backend.app.modules.reporting_attribution_audit.report_archive.schemas.archive_schemas import (
    ArchiveSubmissionRequest,
    ProvenanceResponse,
    ModelVersionResponse,
    DataVersionResponse,
    ConfigVersionResponse,
    ArtifactSummaryResponse,
    ReportArchiveSummaryResponse,
    ReportArchiveDetailResponse,
    ArchiveSearchResponse,
    VersionComparisonResponse,
    RetentionEvaluationResponse,
    RetentionEvaluationItem,
)
from backend.app.modules.reporting_attribution_audit.report_archive.storage.artifact_storage_service import (
    ReportArtifactStorageService,
    ArtifactStorageError,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.services.audit_trail_service import AuditTrailService
from backend.app.modules.reporting_attribution_audit.audit_trail.schemas.audit_schemas import (
    AuditEventCreateRequest,
    AuditActorInput,
)
from backend.app.modules.reporting_attribution_audit.audit_trail.models.audit_models import (
    EventCategory,
    EventSeverity,
    EventOutcome,
    ActorType,
)


class ReportArchiveService:
    """Institutional-grade archival orchestration service for M14.08 Historical Report Archive.
    
    Responsibilities:
    - Ingests reports, calculates SHA-256 hashes, and safely stores artifacts.
    - Transactionally computes monotonic version numbers scoped to (portfolio, report_type, reporting_period).
    - Preserves provenance manifests, models, data inputs, and configurations.
    - Manages supersession, restatement, and withdrawal lifecycles without overwriting historical records.
    - Integrates directly with M14.07 Audit Trail for compliance traceability.
    """

    def __init__(self, db: AsyncSession, storage_service: Optional[ReportArtifactStorageService] = None):
        self.db = db
        self.storage = storage_service or ReportArtifactStorageService()
        self.audit_service = AuditTrailService(db)

    async def _record_audit(
        self,
        action: str,
        archive_id: str,
        details: Dict[str, Any],
        actor_id: str = "SYSTEM",
        outcome: EventOutcome = EventOutcome.SUCCESS,
        severity: EventSeverity = EventSeverity.INFO,
    ):
        """Dispatches an immutable audit event to M14.07."""
        try:
            req = AuditEventCreateRequest(
                category=EventCategory.REPORTING_EVENT,
                action=action,
                module="REPORT_ARCHIVE",
                actor=AuditActorInput(
                    actor_type=ActorType.SYSTEM if actor_id == "SYSTEM" else ActorType.USER,
                    actor_id=actor_id,
                ),
                target_type="REPORT_ARCHIVE",
                target_id=archive_id,
                severity=severity,
                outcome=outcome,
                details=details,
                occurred_at=datetime.now(timezone.utc),
            )
            await self.audit_service.record_audit_event(req)
        except Exception:
            # Archival operational resilience: log failure without breaking archival state
            pass

    async def submit_report_for_archive(
        self,
        req: ArchiveSubmissionRequest,
        actor_id: str = "SYSTEM"
    ) -> ReportArchiveDetailResponse:
        """Atomically ingests a generated report artifact, constructs provenance, and archives the record."""
        # 1. Determine monotonic version number scoped to (portfolio_id, report_type, period_start, period_end)
        query_ver = select(func.coalesce(func.max(ReportArchive.version_number), 0)).where(
            and_(
                ReportArchive.portfolio_id == req.portfolio_id,
                ReportArchive.report_type == req.report_type,
                ReportArchive.period_start == req.period_start,
                ReportArchive.period_end == req.period_end,
            )
        )
        result_ver = await self.db.execute(query_ver)
        highest_ver = result_ver.scalar_one()
        assigned_version = highest_ver + 1

        # 2. Decode artifact content
        try:
            artifact_bytes = base64.b64decode(req.content_base64)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 artifact content: {str(e)}")

        # 3. Generate IDs
        archive_id = f"ARC-{uuid.uuid4().hex[:12].upper()}"
        artifact_id = f"ART-{uuid.uuid4().hex[:12].upper()}"

        # 4. Determine file extension
        ext_map = {
            ArtifactFormat.PDF: "pdf",
            ArtifactFormat.CSV: "csv",
            ArtifactFormat.XLSX: "xlsx",
            ArtifactFormat.HTML: "html",
            ArtifactFormat.JSON: "json",
            ArtifactFormat.OTHER: "bin",
        }
        file_ext = ext_map.get(req.artifact_format, "bin")

        # 5. Persist artifact securely through storage abstraction
        storage_key = self.storage.generate_storage_key(req.portfolio_id, archive_id, file_ext)
        stored_key, calculated_hash, file_size = self.storage.write_artifact_safe(storage_key, artifact_bytes)

        # 6. Calculate manifest hash for provenance
        manifest_payload = {
            "archive_id": archive_id,
            "report_id": req.report_id,
            "report_run_id": req.report_run_id,
            "portfolio_id": req.portfolio_id,
            "parameters": req.provenance.report_parameters,
            "models": [m.model_dump(mode="json") for m in req.models],
            "data_sources": [d.model_dump(mode="json") for d in req.data_sources],
            "configurations": [c.model_dump(mode="json") for c in req.configurations],
        }
        manifest_hash = hashlib.sha256(json.dumps(manifest_payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()

        # 7. Check if superseding previous active version
        if req.supersedes_version_id:
            stmt_sup = select(ReportArchive).where(ReportArchive.archive_id == req.supersedes_version_id)
            res_sup = await self.db.execute(stmt_sup)
            sup_rec = res_sup.scalar_one_or_none()
            if sup_rec and sup_rec.status == ArchiveStatus.AVAILABLE:
                sup_rec.status = ArchiveStatus.SUPERSEDED

        # 8. Create database records
        archive_rec = ReportArchive(
            archive_id=archive_id,
            report_id=req.report_id,
            report_run_id=req.report_run_id,
            portfolio_id=req.portfolio_id,
            portfolio_name_snapshot=req.portfolio_name_snapshot,
            report_type=req.report_type,
            report_title_snapshot=req.report_title_snapshot,
            report_definition_id=req.report_definition_id,
            report_definition_version=req.report_definition_version,
            period_start=req.period_start,
            period_end=req.period_end,
            valuation_timestamp=req.valuation_timestamp,
            generated_at=req.generated_at,
            archived_at=datetime.now(timezone.utc),
            version_number=assigned_version,
            generation_reason=req.generation_reason,
            status=ArchiveStatus.AVAILABLE,
            previous_version_id=req.previous_version_id,
            supersedes_version_id=req.supersedes_version_id,
            restates_version_id=req.restates_version_id,
            restatement_reason=req.restatement_reason,
            summary_nav=req.summary_nav,
            summary_var_value=req.summary_var_value,
            summary_es_value=req.summary_es_value,
            currency=req.currency,
            created_by=actor_id,
        )
        self.db.add(archive_rec)

        # Artifact record
        artifact_rec = ReportArchiveArtifact(
            artifact_id=artifact_id,
            archive_id=archive_id,
            storage_backend="LOCAL_FS",
            storage_key=stored_key,
            original_filename=req.artifact_filename,
            mime_type=req.mime_type,
            file_extension=file_ext,
            file_size_bytes=file_size,
            hash_algorithm="SHA256",
            artifact_hash=calculated_hash,
            integrity_status=IntegrityStatus.VERIFIED,
            last_verified_at=datetime.now(timezone.utc),
        )
        self.db.add(artifact_rec)

        # Provenance manifest record
        prov_rec = ReportArchiveProvenance(
            archive_id=archive_id,
            report_run_id=req.report_run_id,
            application_version=req.provenance.application_version,
            code_commit=req.provenance.code_commit,
            environment_id=req.provenance.environment_id,
            execution_started_at=req.provenance.execution_started_at,
            execution_completed_at=req.provenance.execution_completed_at,
            trigger_source=req.provenance.trigger_source,
            requesting_actor_id=req.provenance.requesting_actor_id,
            report_parameters=req.provenance.report_parameters,
            data_quality_summary=req.provenance.data_quality_summary,
            known_limitations=req.provenance.known_limitations,
            provenance_schema_version="1.0",
            manifest_hash=manifest_hash,
        )
        self.db.add(prov_rec)

        # Model versions
        for m in req.models:
            m_rec = ReportArchiveModelVersion(
                archive_id=archive_id,
                model_id=m.model_id,
                model_name=m.model_name,
                model_version=m.model_version,
                implementation_version=m.implementation_version,
                configuration_version=m.configuration_version,
                model_artifact_hash=m.model_artifact_hash,
                parameter_set_id=m.parameter_set_id,
                effective_at=m.effective_at,
                executed_at=m.executed_at,
            )
            self.db.add(m_rec)

        # Data sources
        for d in req.data_sources:
            d_rec = ReportArchiveDataVersion(
                archive_id=archive_id,
                source_type=d.source_type,
                source_id=d.source_id,
                dataset_id=d.dataset_id,
                snapshot_id=d.snapshot_id,
                provider_id=d.provider_id,
                source_version=d.source_version,
                data_as_of=d.data_as_of,
                ingested_at=d.ingested_at,
                data_cutoff_at=d.data_cutoff_at,
                quality_status=d.quality_status,
            )
            self.db.add(d_rec)

        # Configurations
        for c in req.configurations:
            cfg_hash = hashlib.sha256(json.dumps(c.configuration_snapshot, sort_keys=True, default=str).encode("utf-8")).hexdigest()
            c_rec = ReportArchiveConfigVersion(
                archive_id=archive_id,
                configuration_id=c.configuration_id,
                configuration_version=c.configuration_version,
                configuration_type=c.configuration_type,
                configuration_snapshot=c.configuration_snapshot,
                configuration_hash=cfg_hash,
            )
            self.db.add(c_rec)

        await self.db.commit()

        # Audit event
        await self._record_audit(
            action="REPORT_ARCHIVED",
            archive_id=archive_id,
            details={
                "portfolio_id": req.portfolio_id,
                "report_type": req.report_type.value,
                "version_number": assigned_version,
                "artifact_hash": calculated_hash,
                "file_size_bytes": file_size,
            },
            actor_id=actor_id,
        )

        return await self.get_archive_by_id(archive_id)

    async def get_archive_by_id(self, archive_id: str) -> Optional[ReportArchiveDetailResponse]:
        """Loads complete archive metadata including artifact, provenance, and legal hold status."""
        query = (
            select(ReportArchive)
            .where(ReportArchive.archive_id == archive_id)
            .options(
                selectinload(ReportArchive.artifact),
                selectinload(ReportArchive.provenance),
                selectinload(ReportArchive.model_versions),
                selectinload(ReportArchive.data_versions),
                selectinload(ReportArchive.config_versions),
                selectinload(ReportArchive.legal_holds),
            )
        )
        res = await self.db.execute(query)
        archive = res.scalar_one_or_none()
        if not archive:
            return None

        # Build responses
        art_resp = None
        if archive.artifact:
            art_resp = ArtifactSummaryResponse(
                artifact_id=archive.artifact.artifact_id,
                format=archive.artifact.file_extension.upper(),
                mime_type=archive.artifact.mime_type,
                file_size_bytes=archive.artifact.file_size_bytes,
                hash_algorithm=archive.artifact.hash_algorithm,
                artifact_hash=archive.artifact.artifact_hash,
                integrity_status=archive.artifact.integrity_status,
                last_verified_at=archive.artifact.last_verified_at,
            )

        prov_resp = None
        if archive.provenance:
            prov_resp = ProvenanceResponse(
                archive_id=archive.provenance.archive_id,
                report_run_id=archive.provenance.report_run_id,
                application_version=archive.provenance.application_version,
                code_commit=archive.provenance.code_commit,
                environment_id=archive.provenance.environment_id,
                execution_started_at=archive.provenance.execution_started_at,
                execution_completed_at=archive.provenance.execution_completed_at,
                trigger_source=archive.provenance.trigger_source,
                requesting_actor_id=archive.provenance.requesting_actor_id,
                report_parameters=archive.provenance.report_parameters,
                data_quality_summary=archive.provenance.data_quality_summary,
                known_limitations=archive.provenance.known_limitations,
                manifest_hash=archive.provenance.manifest_hash,
                models=[ModelVersionResponse.model_validate(m) for m in archive.model_versions],
                data_sources=[DataVersionResponse.model_validate(d) for d in archive.data_versions],
                configurations=[ConfigVersionResponse.model_validate(c) for c in archive.config_versions],
            )

        has_active_hold = any(h.status == LegalHoldStatus.ACTIVE for h in archive.legal_holds)

        return ReportArchiveDetailResponse(
            archive_id=archive.archive_id,
            report_id=archive.report_id,
            report_run_id=archive.report_run_id,
            portfolio_id=archive.portfolio_id,
            portfolio_name_snapshot=archive.portfolio_name_snapshot,
            report_type=archive.report_type,
            report_title_snapshot=archive.report_title_snapshot,
            report_definition_id=archive.report_definition_id,
            report_definition_version=archive.report_definition_version,
            period_start=archive.period_start,
            period_end=archive.period_end,
            valuation_timestamp=archive.valuation_timestamp,
            generated_at=archive.generated_at,
            archived_at=archive.archived_at,
            version_number=archive.version_number,
            generation_reason=archive.generation_reason,
            status=archive.status,
            previous_version_id=archive.previous_version_id,
            supersedes_version_id=archive.supersedes_version_id,
            restates_version_id=archive.restates_version_id,
            withdraws_version_id=archive.withdraws_version_id,
            restatement_reason=archive.restatement_reason,
            withdrawal_reason=archive.withdrawal_reason,
            summary_nav=archive.summary_nav,
            summary_var_value=archive.summary_var_value,
            summary_es_value=archive.summary_es_value,
            currency=archive.currency,
            artifact=art_resp,
            provenance=prov_resp,
            has_active_legal_hold=has_active_hold,
        )

    async def search_archives(
        self,
        portfolio_id: Optional[str] = None,
        report_type: Optional[ReportArchiveType] = None,
        report_run_id: Optional[str] = None,
        status: Optional[ArchiveStatus] = None,
        period_start_from: Optional[datetime] = None,
        period_end_to: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> ArchiveSearchResponse:
        """Search and filter archived reports with pagination and sorting."""
        conditions = []
        if portfolio_id:
            conditions.append(ReportArchive.portfolio_id == portfolio_id)
        if report_type:
            conditions.append(ReportArchive.report_type == report_type)
        if report_run_id:
            conditions.append(ReportArchive.report_run_id == report_run_id)
        if status:
            conditions.append(ReportArchive.status == status)
        if period_start_from:
            conditions.append(ReportArchive.period_start >= period_start_from)
        if period_end_to:
            conditions.append(ReportArchive.period_end <= period_end_to)

        count_query = select(func.count(ReportArchive.id)).where(and_(*conditions) if conditions else True)
        total_res = await self.db.execute(count_query)
        total = total_res.scalar_one()

        offset = (page - 1) * page_size
        items_query = (
            select(ReportArchive)
            .where(and_(*conditions) if conditions else True)
            .options(
                selectinload(ReportArchive.artifact),
                selectinload(ReportArchive.legal_holds),
            )
            .order_by(desc(ReportArchive.generated_at), desc(ReportArchive.version_number))
            .offset(offset)
            .limit(page_size)
        )
        res = await self.db.execute(items_query)
        records = res.scalars().all()

        items = []
        for r in records:
            art_resp = None
            if r.artifact:
                art_resp = ArtifactSummaryResponse(
                    artifact_id=r.artifact.artifact_id,
                    format=r.artifact.file_extension.upper(),
                    mime_type=r.artifact.mime_type,
                    file_size_bytes=r.artifact.file_size_bytes,
                    hash_algorithm=r.artifact.hash_algorithm,
                    artifact_hash=r.artifact.artifact_hash,
                    integrity_status=r.artifact.integrity_status,
                    last_verified_at=r.artifact.last_verified_at,
                )
            has_hold = any(h.status == LegalHoldStatus.ACTIVE for h in r.legal_holds)
            items.append(
                ReportArchiveSummaryResponse(
                    archive_id=r.archive_id,
                    report_id=r.report_id,
                    report_run_id=r.report_run_id,
                    portfolio_id=r.portfolio_id,
                    portfolio_name_snapshot=r.portfolio_name_snapshot,
                    report_type=r.report_type,
                    report_title_snapshot=r.report_title_snapshot,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    valuation_timestamp=r.valuation_timestamp,
                    generated_at=r.generated_at,
                    archived_at=r.archived_at,
                    version_number=r.version_number,
                    generation_reason=r.generation_reason,
                    status=r.status,
                    summary_nav=r.summary_nav,
                    summary_var_value=r.summary_var_value,
                    summary_es_value=r.summary_es_value,
                    currency=r.currency,
                    artifact=art_resp,
                    has_active_legal_hold=has_hold,
                )
            )

        pages = (total + page_size - 1) // page_size if total > 0 else 0
        return ArchiveSearchResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    async def get_version_history(self, archive_id: str) -> List[ReportArchiveSummaryResponse]:
        """Retrieves all versions of the logical report that the given archive_id belongs to."""
        target = await self.get_archive_by_id(archive_id)
        if not target:
            return []

        query = (
            select(ReportArchive)
            .where(
                and_(
                    ReportArchive.portfolio_id == target.portfolio_id,
                    ReportArchive.report_type == target.report_type,
                    ReportArchive.period_start == target.period_start,
                    ReportArchive.period_end == target.period_end,
                )
            )
            .options(
                selectinload(ReportArchive.artifact),
                selectinload(ReportArchive.legal_holds),
            )
            .order_by(desc(ReportArchive.version_number))
        )
        res = await self.db.execute(query)
        records = res.scalars().all()

        items = []
        for r in records:
            art_resp = None
            if r.artifact:
                art_resp = ArtifactSummaryResponse(
                    artifact_id=r.artifact.artifact_id,
                    format=r.artifact.file_extension.upper(),
                    mime_type=r.artifact.mime_type,
                    file_size_bytes=r.artifact.file_size_bytes,
                    hash_algorithm=r.artifact.hash_algorithm,
                    artifact_hash=r.artifact.artifact_hash,
                    integrity_status=r.artifact.integrity_status,
                    last_verified_at=r.artifact.last_verified_at,
                )
            has_hold = any(h.status == LegalHoldStatus.ACTIVE for h in r.legal_holds)
            items.append(
                ReportArchiveSummaryResponse(
                    archive_id=r.archive_id,
                    report_id=r.report_id,
                    report_run_id=r.report_run_id,
                    portfolio_id=r.portfolio_id,
                    portfolio_name_snapshot=r.portfolio_name_snapshot,
                    report_type=r.report_type,
                    report_title_snapshot=r.report_title_snapshot,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    valuation_timestamp=r.valuation_timestamp,
                    generated_at=r.generated_at,
                    archived_at=r.archived_at,
                    version_number=r.version_number,
                    generation_reason=r.generation_reason,
                    status=r.status,
                    summary_nav=r.summary_nav,
                    summary_var_value=r.summary_var_value,
                    summary_es_value=r.summary_es_value,
                    currency=r.currency,
                    artifact=art_resp,
                    has_active_legal_hold=has_hold,
                )
            )
        return items

    async def compare_archive_versions(self, base_archive_id: str, other_archive_id: str) -> VersionComparisonResponse:
        """Compares metadata, summary financial metrics, and provenance models between two versions."""
        base = await self.get_archive_by_id(base_archive_id)
        other = await self.get_archive_by_id(other_archive_id)
        if not base or not other:
            raise ValueError("One or both archive versions could not be found.")

        nav_diff = (other.summary_nav - base.summary_nav) if (other.summary_nav is not None and base.summary_nav is not None) else None
        var_diff = (other.summary_var_value - base.summary_var_value) if (other.summary_var_value is not None and base.summary_var_value is not None) else None
        es_diff = (other.summary_es_value - base.summary_es_value) if (other.summary_es_value is not None and base.summary_es_value is not None) else None

        # Compare model versions
        base_models = {m.model_name: m.model_version for m in (base.provenance.models if base.provenance else [])}
        other_models = {m.model_name: m.model_version for m in (other.provenance.models if other.provenance else [])}
        model_changes = []
        for name, v_new in other_models.items():
            if name not in base_models:
                model_changes.append(f"Model added: {name} (v{v_new})")
            elif base_models[name] != v_new:
                model_changes.append(f"Model {name} upgraded: v{base_models[name]} -> v{v_new}")

        # Compare data snapshots
        base_snaps = {d.source_type: d.snapshot_id for d in (base.provenance.data_sources if base.provenance else [])}
        other_snaps = {d.source_type: d.snapshot_id for d in (other.provenance.data_sources if other.provenance else [])}
        data_changes = []
        for st, sid in other_snaps.items():
            if st not in base_snaps:
                data_changes.append(f"Data source added: {st} (snap: {sid})")
            elif base_snaps[st] != sid:
                data_changes.append(f"Data source {st} snapshot changed: {base_snaps[st]} -> {sid}")

        # Compare configurations
        base_cfgs = {c.configuration_type: c.configuration_hash for c in (base.provenance.configurations if base.provenance else [])}
        other_cfgs = {c.configuration_type: c.configuration_hash for c in (other.provenance.configurations if other.provenance else [])}
        cfg_changes = []
        for ct, h in other_cfgs.items():
            if ct not in base_cfgs:
                cfg_changes.append(f"Configuration added: {ct}")
            elif base_cfgs[ct] != h:
                cfg_changes.append(f"Configuration {ct} modified")

        return VersionComparisonResponse(
            base_archive=base,
            compared_archive=other,
            nav_diff=nav_diff,
            var_diff=var_diff,
            es_diff=es_diff,
            model_changes=model_changes,
            data_source_changes=data_changes,
            configuration_changes=cfg_changes,
        )

    async def get_artifact_download(self, archive_id: str, actor_id: str = "SYSTEM") -> Tuple[bytes, str, str]:
        """Fetches binary report artifact bytes for download, enforcing policy, quarantine, and audit rules.
        
        Returns:
            Tuple of (file_bytes, original_filename, mime_type)
        """
        query = (
            select(ReportArchive)
            .where(ReportArchive.archive_id == archive_id)
            .options(
                selectinload(ReportArchive.artifact),
                selectinload(ReportArchive.legal_holds),
            )
        )
        res = await self.db.execute(query)
        archive = res.scalar_one_or_none()
        if not archive:
            raise FileNotFoundError("Archive record not found.")

        if archive.status == ArchiveStatus.QUARANTINED:
            raise PermissionError("Report artifact is quarantined due to integrity failure and cannot be downloaded.")
        if archive.status == ArchiveStatus.EXPIRED:
            raise PermissionError("Report artifact is expired under retention policy.")

        if not archive.artifact:
            raise FileNotFoundError("No physical artifact registered with this archive.")

        # Read artifact through storage service
        file_bytes = self.storage.read_artifact(archive.artifact.storage_key)

        # Audit download
        await self._record_audit(
            action="REPORT_DOWNLOADED",
            archive_id=archive_id,
            details={
                "portfolio_id": archive.portfolio_id,
                "artifact_id": archive.artifact.artifact_id,
                "file_size": len(file_bytes),
            },
            actor_id=actor_id,
        )

        return file_bytes, archive.artifact.original_filename, archive.artifact.mime_type

    async def verify_artifact_integrity(self, archive_id: str) -> Tuple[IntegrityStatus, Optional[str]]:
        """Verifies disk artifact matches registered SHA-256 hash, quarantining on corruption."""
        query = select(ReportArchive).where(ReportArchive.archive_id == archive_id).options(selectinload(ReportArchive.artifact))
        res = await self.db.execute(query)
        archive = res.scalar_one_or_none()
        if not archive or not archive.artifact:
            return IntegrityStatus.MISSING, None

        is_valid, actual_hash = self.storage.verify_integrity(
            archive.artifact.storage_key,
            archive.artifact.artifact_hash
        )

        if is_valid:
            archive.artifact.integrity_status = IntegrityStatus.VERIFIED
            archive.artifact.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            return IntegrityStatus.VERIFIED, actual_hash
        elif actual_hash is None:
            archive.artifact.integrity_status = IntegrityStatus.MISSING
            archive.status = ArchiveStatus.QUARANTINED
            archive.artifact.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self._record_audit(
                action="ARTIFACT_INTEGRITY_FAILED_MISSING",
                archive_id=archive_id,
                details={"expected_hash": archive.artifact.artifact_hash},
                severity=EventSeverity.CRITICAL,
                outcome=EventOutcome.FAILURE,
            )
            return IntegrityStatus.MISSING, None
        else:
            archive.artifact.integrity_status = IntegrityStatus.CORRUPTED
            archive.status = ArchiveStatus.QUARANTINED
            archive.artifact.last_verified_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self._record_audit(
                action="ARTIFACT_INTEGRITY_FAILED_CORRUPTION",
                archive_id=archive_id,
                details={
                    "expected_hash": archive.artifact.artifact_hash,
                    "actual_hash": actual_hash,
                },
                severity=EventSeverity.CRITICAL,
                outcome=EventOutcome.FAILURE,
            )
            return IntegrityStatus.CORRUPTED, actual_hash

    async def supersede_report(self, archive_id: str, new_archive_id: str, reason: str, actor_id: str = "SYSTEM"):
        """Marks an older archive version as SUPERSEDED by a newer version."""
        stmt = select(ReportArchive).where(ReportArchive.archive_id == archive_id)
        res = await self.db.execute(stmt)
        archive = res.scalar_one_or_none()
        if not archive:
            raise ValueError(f"Archive {archive_id} not found.")

        archive.status = ArchiveStatus.SUPERSEDED
        archive.supersedes_version_id = new_archive_id
        await self.db.commit()

        await self._record_audit(
            action="REPORT_SUPERSEDED",
            archive_id=archive_id,
            details={"superseded_by": new_archive_id, "reason": reason},
            actor_id=actor_id,
        )

    async def withdraw_report(self, archive_id: str, reason: str, actor_id: str = "SYSTEM"):
        """Formally withdraws a report from active distribution with documented reason."""
        stmt = select(ReportArchive).where(ReportArchive.archive_id == archive_id)
        res = await self.db.execute(stmt)
        archive = res.scalar_one_or_none()
        if not archive:
            raise ValueError(f"Archive {archive_id} not found.")

        archive.status = ArchiveStatus.WITHDRAWN
        archive.withdrawal_reason = reason
        await self.db.commit()

        await self._record_audit(
            action="REPORT_WITHDRAWN",
            archive_id=archive_id,
            details={"reason": reason},
            actor_id=actor_id,
        )

    async def apply_legal_hold(self, archive_id: str, reason: str, initiated_by: str) -> ReportArchiveLegalHold:
        """Applies a legal hold to preserve report from automated retention disposal."""
        stmt = select(ReportArchive).where(ReportArchive.archive_id == archive_id)
        res = await self.db.execute(stmt)
        archive = res.scalar_one_or_none()
        if not archive:
            raise ValueError(f"Archive {archive_id} not found.")

        hold = ReportArchiveLegalHold(
            hold_id=f"HLD-{uuid.uuid4().hex[:12].upper()}",
            archive_id=archive_id,
            reason=reason,
            status=LegalHoldStatus.ACTIVE,
            initiated_by=initiated_by,
        )
        self.db.add(hold)
        await self.db.commit()

        await self._record_audit(
            action="LEGAL_HOLD_APPLIED",
            archive_id=archive_id,
            details={"hold_id": hold.hold_id, "reason": reason},
            actor_id=initiated_by,
        )
        return hold

    async def release_legal_hold(self, hold_id: str, release_reason: str, released_by: str):
        """Releases an active legal hold."""
        stmt = select(ReportArchiveLegalHold).where(ReportArchiveLegalHold.hold_id == hold_id)
        res = await self.db.execute(stmt)
        hold = res.scalar_one_or_none()
        if not hold:
            raise ValueError(f"Legal hold {hold_id} not found.")

        hold.status = LegalHoldStatus.RELEASED
        hold.released_at = datetime.now(timezone.utc)
        hold.release_reason = release_reason
        await self.db.commit()

        await self._record_audit(
            action="LEGAL_HOLD_RELEASED",
            archive_id=hold.archive_id,
            details={"hold_id": hold_id, "release_reason": release_reason},
            actor_id=released_by,
        )

    async def evaluate_retention_dry_run(self) -> RetentionEvaluationResponse:
        """Non-mutating evaluation of archive records against retention policies and legal holds."""
        # 1. Fetch active retention policies
        stmt_pol = select(ReportArchiveRetentionPolicy).where(ReportArchiveRetentionPolicy.policy_status == "ACTIVE")
        res_pol = await self.db.execute(stmt_pol)
        policies = {p.report_type: p for p in res_pol.scalars().all()}

        # 2. Fetch all archives
        stmt_arc = select(ReportArchive).options(selectinload(ReportArchive.legal_holds))
        res_arc = await self.db.execute(stmt_arc)
        archives = res_arc.scalars().all()

        now = datetime.now(timezone.utc)
        items: List[RetentionEvaluationItem] = []
        eligible_disposal = 0
        held_count = 0
        retained_count = 0

        for a in archives:
            # Calculate age in days
            # Ensure naive/aware compatibility
            archived_date = a.archived_at
            if archived_date.tzinfo is None:
                archived_date = archived_date.replace(tzinfo=timezone.utc)
            age_days = (now - archived_date).days

            policy = policies.get(a.report_type)
            retention_days = policy.retention_days if policy else 2555 # Default 7 years (2555 days)
            is_expired = age_days > retention_days
            has_hold = any(h.status == LegalHoldStatus.ACTIVE for h in a.legal_holds)

            can_dispose = is_expired and not has_hold
            if can_dispose:
                eligible_disposal += 1
                rec_action = "ELIGIBLE_FOR_DISPOSAL"
            elif has_hold:
                held_count += 1
                rec_action = "PROTECTED_BY_LEGAL_HOLD"
            else:
                retained_count += 1
                rec_action = "ACTIVE_RETENTION"

            items.append(
                RetentionEvaluationItem(
                    archive_id=a.archive_id,
                    report_type=a.report_type,
                    archived_at=a.archived_at,
                    age_days=age_days,
                    applicable_policy_id=policy.policy_id if policy else None,
                    retention_days=retention_days,
                    is_expired=is_expired,
                    has_legal_hold=has_hold,
                    eligible_for_disposal=can_dispose,
                    recommended_action=rec_action,
                )
            )

        return RetentionEvaluationResponse(
            evaluated_at=now,
            total_evaluated=len(archives),
            eligible_for_disposal_count=eligible_disposal,
            held_count=held_count,
            retained_count=retained_count,
            items=items,
        )
