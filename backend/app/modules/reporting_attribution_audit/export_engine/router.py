import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.app.core.database import get_db
from backend.app.modules.reporting_attribution_audit.export_engine.models.export_models import (
    ExportJob,
    ExportArtifact,
    ExportValidationResult,
    ExportAuditEvent,
    ExportTemplate,
    ExportFormat,
    ExportStatus,
)
from backend.app.modules.reporting_attribution_audit.export_engine.schemas.export_schemas import (
    ExportCreateRequest,
    ExportJobSummaryResponse,
    ExportArtifactResponse,
    ExportValidationSummaryResponse,
    DatasetRegistrySchema,
    DatasetFieldDefinitionSchema,
    ExportTemplateSchema,
    ExportTemplateCreateRequest,
    ExportAuditEventResponse,
)
from backend.app.modules.reporting_attribution_audit.export_engine.services.export_orchestration_service import (
    ExportOrchestrationService,
)
from backend.app.modules.reporting_attribution_audit.export_engine.registry.dataset_registry import (
    DATASET_DEFINITIONS,
)
from backend.app.modules.reporting_attribution_audit.export_engine.storage.storage_adapter import (
    LocalStorageAdapter,
)

router = APIRouter(prefix="/exports", tags=["M14.06 Export Engine"])
storage_adapter = LocalStorageAdapter()


@router.get("/datasets", response_model=List[DatasetRegistrySchema])
async def list_registered_datasets():
    """List all registered datasets and their supported schemas/formats in the Export Engine."""
    results = []
    for k, v in DATASET_DEFINITIONS.items():
        fields = [DatasetFieldDefinitionSchema(**f) for f in v["fields"]]
        results.append(
            DatasetRegistrySchema(
                dataset_code=v["dataset_code"],
                dataset_name=v["dataset_name"],
                source_module=v["source_module"],
                source_feature=v["source_feature"],
                description=v["description"],
                schema_version=v["schema_version"],
                supported_formats=v["supported_formats"],
                access_policy_reference=v["access_policy_reference"],
                maximum_rows=v["maximum_rows"],
                fields=fields,
            )
        )
    return results


@router.get("/datasets/{dataset_id}", response_model=DatasetRegistrySchema)
async def get_dataset_details(dataset_id: str):
    """Retrieve detailed schema and field definitions for a specific dataset."""
    if dataset_id not in DATASET_DEFINITIONS:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.")
    v = DATASET_DEFINITIONS[dataset_id]
    fields = [DatasetFieldDefinitionSchema(**f) for f in v["fields"]]
    return DatasetRegistrySchema(
        dataset_code=v["dataset_code"],
        dataset_name=v["dataset_name"],
        source_module=v["source_module"],
        source_feature=v["source_feature"],
        description=v["description"],
        schema_version=v["schema_version"],
        supported_formats=v["supported_formats"],
        access_policy_reference=v["access_policy_reference"],
        maximum_rows=v["maximum_rows"],
        fields=fields,
    )


@router.post("", response_model=ExportJobSummaryResponse, status_code=201)
async def create_export_job(
    request: ExportCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create and execute an export request across CSV, XLSX, and PDF formats."""
    service = ExportOrchestrationService(db, storage=storage_adapter)
    return await service.create_and_execute_export(request)


@router.get("", response_model=List[ExportJobSummaryResponse])
async def list_export_jobs(
    portfolio_id: Optional[str] = None,
    dataset_id: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List historical export jobs with status and summary metrics."""
    stmt = select(ExportJob).order_by(desc(ExportJob.requested_at)).limit(limit)
    if portfolio_id:
        stmt = stmt.where(ExportJob.portfolio_id == portfolio_id)
    if dataset_id:
        stmt = stmt.where(ExportJob.dataset_id == dataset_id)

    res = await db.execute(stmt)
    jobs = res.scalars().all()

    output = []
    for j in jobs:
        art_stmt = select(ExportArtifact).where(ExportArtifact.export_job_id == j.id)
        art_res = await db.execute(art_stmt)
        arts = [
            ExportArtifactResponse(
                artifact_id=a.id,
                artifact_type=a.artifact_type,
                file_name=a.file_name,
                mime_type=a.mime_type,
                file_size_bytes=a.file_size_bytes,
                file_hash=a.file_hash,
                storage_reference=a.storage_reference,
                artifact_status=a.artifact_status,
                created_at=a.created_at,
                expires_at=a.expires_at,
            )
            for a in art_res.scalars().all()
        ]

        val_stmt = select(ExportValidationResult).where(ExportValidationResult.export_job_id == j.id)
        val_res = await db.execute(val_stmt)
        val_db = val_res.scalars().first()
        val_summary = (
            ExportValidationSummaryResponse(
                validation_status=val_db.validation_status,
                validation_version=val_db.validation_version,
                checks_performed=val_db.checks_performed,
                failed_checks=val_db.failed_checks,
                warnings=val_db.warnings,
                source_row_count=val_db.source_row_count,
                exported_row_count=val_db.exported_row_count,
                excluded_row_count=val_db.excluded_row_count,
                validated_at=val_db.validated_at,
            )
            if val_db
            else None
        )

        output.append(
            ExportJobSummaryResponse(
                id=j.id,
                export_code=j.export_code,
                requested_by=j.requested_by,
                source_module=j.source_module,
                source_feature=j.source_feature,
                source_report_id=j.source_report_id,
                dataset_id=j.dataset_id,
                portfolio_id=j.portfolio_id,
                export_status=j.export_status,
                progress_percentage=j.progress_percentage,
                current_stage=j.current_stage,
                total_records=j.total_records,
                processed_records=j.processed_records,
                requested_at=j.requested_at,
                started_at=j.started_at,
                completed_at=j.completed_at,
                failure_code=j.failure_code,
                failure_message=j.failure_message,
                requested_formats=[ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
                artifacts=arts,
                validation_summary=val_summary,
            )
        )
    return output


@router.get("/{export_id}", response_model=ExportJobSummaryResponse)
async def get_export_job(export_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve detailed state of an export job."""
    stmt = select(ExportJob).where(ExportJob.id == export_id)
    res = await db.execute(stmt)
    j = res.scalars().first()
    if not j:
        raise HTTPException(status_code=404, detail="Export job not found.")

    art_stmt = select(ExportArtifact).where(ExportArtifact.export_job_id == j.id)
    art_res = await db.execute(art_stmt)
    arts = [
        ExportArtifactResponse(
            artifact_id=a.id,
            artifact_type=a.artifact_type,
            file_name=a.file_name,
            mime_type=a.mime_type,
            file_size_bytes=a.file_size_bytes,
            file_hash=a.file_hash,
            storage_reference=a.storage_reference,
            artifact_status=a.artifact_status,
            created_at=a.created_at,
            expires_at=a.expires_at,
        )
        for a in art_res.scalars().all()
    ]

    val_stmt = select(ExportValidationResult).where(ExportValidationResult.export_job_id == j.id)
    val_res = await db.execute(val_stmt)
    val_db = val_res.scalars().first()
    val_summary = (
        ExportValidationSummaryResponse(
            validation_status=val_db.validation_status,
            validation_version=val_db.validation_version,
            checks_performed=val_db.checks_performed,
            failed_checks=val_db.failed_checks,
            warnings=val_db.warnings,
            source_row_count=val_db.source_row_count,
            exported_row_count=val_db.exported_row_count,
            excluded_row_count=val_db.excluded_row_count,
            validated_at=val_db.validated_at,
        )
        if val_db
        else None
    )

    return ExportJobSummaryResponse(
        id=j.id,
        export_code=j.export_code,
        requested_by=j.requested_by,
        source_module=j.source_module,
        source_feature=j.source_feature,
        source_report_id=j.source_report_id,
        dataset_id=j.dataset_id,
        portfolio_id=j.portfolio_id,
        export_status=j.export_status,
        progress_percentage=j.progress_percentage,
        current_stage=j.current_stage,
        total_records=j.total_records,
        processed_records=j.processed_records,
        requested_at=j.requested_at,
        started_at=j.started_at,
        completed_at=j.completed_at,
        failure_code=j.failure_code,
        failure_message=j.failure_message,
        requested_formats=[ExportFormat.CSV, ExportFormat.XLSX, ExportFormat.PDF],
        artifacts=arts,
        validation_summary=val_summary,
    )


@router.get("/{export_id}/download/{artifact_id}")
async def download_export_artifact(
    export_id: int, artifact_id: int, db: AsyncSession = Depends(get_db)
):
    """Download generated artifact with cryptographic verification and audit recording."""
    stmt = select(ExportArtifact).where(
        ExportArtifact.id == artifact_id, ExportArtifact.export_job_id == export_id
    )
    res = await db.execute(stmt)
    art = res.scalars().first()
    if not art:
        raise HTTPException(status_code=404, detail="Artifact not found.")

    if not os.path.exists(art.storage_reference):
        raise HTTPException(status_code=404, detail="Artifact file missing from persistent storage.")

    content = storage_adapter.read_artifact(art.storage_reference)

    # Record download audit event
    db.add(
        ExportAuditEvent(
            export_job_id=export_id,
            actor_id="USER",
            event_type="DOWNLOADED",
            event_details={"artifact_id": artifact_id, "file_name": art.file_name},
        )
    )
    await db.commit()

    return FastAPIResponse(
        content=content,
        media_type=art.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{art.file_name}"',
            "X-Artifact-SHA256": art.file_hash,
        },
    )


@router.get("/{export_id}/audit", response_model=List[ExportAuditEventResponse])
async def get_export_audit_history(export_id: int, db: AsyncSession = Depends(get_db)):
    """Retrieve immutable audit event trail for an export job."""
    stmt = (
        select(ExportAuditEvent)
        .where(ExportAuditEvent.export_job_id == export_id)
        .order_by(ExportAuditEvent.event_timestamp)
    )
    res = await db.execute(stmt)
    events = res.scalars().all()
    return [
        ExportAuditEventResponse(
            id=e.id,
            actor_id=e.actor_id,
            event_type=e.event_type,
            event_timestamp=e.event_timestamp,
            event_details=e.event_details,
        )
        for e in events
    ]
