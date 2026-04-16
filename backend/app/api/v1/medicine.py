from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status

from app.api.crud import build_crud_router
from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.core.config import get_settings
from app.core.exceptions import ValidationError
from app.db.pool import Database
from app.repositories.medicine import (
    MedicineArrivalRepository,
    MedicineBatchRepository,
    MedicineConsumptionRepository,
    MedicineTypeRepository,
)
from app.services.medicine import (
    MedicineArrivalService,
    MedicineBatchService,
    MedicineConsumptionService,
    MedicineTypeService,
)
from app.services.storage import get_storage_service
from app.utils.auth_tokens import TokenError, create_signed_token, decode_signed_token


router = APIRouter(prefix="/medicine", tags=["medicine"])

PUBLIC_MEDICINE_TOKEN_TYPE = "medicine_public_batch"
FILENAME_SANITIZER_RE = re.compile(r"[^A-Za-z0-9._-]+")
PRIVILEGED_SCOPE_ROLES = {"super_admin", "admin", "manager"}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _actor_bypasses_department_scope(actor: CurrentActor) -> bool:
    return any(
        role in PRIVILEGED_SCOPE_ROLES or role.endswith("-manager")
        for role in actor.roles
    )


def _sanitize_filename(filename: str, *, fallback: str = "file") -> str:
    stripped = str(filename or "").strip()
    if not stripped:
        return fallback
    normalized = FILENAME_SANITIZER_RE.sub("_", stripped).strip("._")
    return normalized or fallback


def _build_public_subject(*, organization_id: str, batch_id: str) -> str:
    return f"{organization_id}:{batch_id}"


def _parse_public_subject(subject: str) -> tuple[str, str]:
    parts = str(subject or "").strip().split(":", 1)
    if len(parts) != 2:
        raise TokenError("Invalid token subject")
    organization_id, batch_id = parts
    try:
        return str(UUID(organization_id)), str(UUID(batch_id))
    except ValueError as exc:
        raise TokenError("Invalid token subject") from exc


def _build_public_url(token: str) -> str:
    settings = get_settings()
    base = settings.public_web_base_url.strip().rstrip("/")
    if not base:
        return f"/public/medicine/{token}"
    return f"{base}/public/medicine/{token}"


def _build_qr_storage_key(*, organization_id: str, batch_id: str) -> str:
    return f"medicine/{organization_id}/batches/{batch_id}/qr/public.png"


def _build_attachment_storage_key(*, organization_id: str, batch_id: str, filename: str) -> str:
    safe_filename = _sanitize_filename(filename, fallback="attachment")
    return f"medicine/{organization_id}/batches/{batch_id}/attachments/{uuid4().hex}-{safe_filename}"


def _encode_image_data_url(image_bytes: bytes, content_type: str = "image/png") -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{encoded}"


def _build_public_attachment_url(token: str) -> str:
    return f"/api/v1/medicine/public/batches/{token}/attachment"


def _build_public_batch_payload(
    row: dict[str, Any],
    *,
    token: str,
) -> dict[str, Any]:
    supplier_name = (
        str(row.get("supplier_company_name") or "").strip()
        or " ".join(
            [
                str(row.get("supplier_first_name") or "").strip(),
                str(row.get("supplier_last_name") or "").strip(),
            ]
        ).strip()
        or None
    )

    attachment_key = str(row.get("attachment_key") or "").strip()
    attachment_payload = None
    if attachment_key:
        attachment_payload = {
            "name": row.get("attachment_name"),
            "content_type": row.get("attachment_content_type"),
            "size_bytes": row.get("attachment_size_bytes"),
            "url": _build_public_attachment_url(token),
        }

    return {
        "id": str(row["id"]),
        "batch_code": row.get("batch_code"),
        "barcode": row.get("barcode"),
        "expiry_date": row.get("expiry_date"),
        "arrived_on": row.get("arrived_on"),
        "received_quantity": row.get("received_quantity"),
        "remaining_quantity": row.get("remaining_quantity"),
        "unit": row.get("unit"),
        "unit_cost": row.get("unit_cost"),
        "currency": row.get("currency"),
        "note": row.get("note"),
        "token_expires_at": row.get("qr_token_expires_at"),
        "medicine_type": {
            "id": str(row["medicine_type_id"]),
            "name": row.get("medicine_type_name"),
            "code": row.get("medicine_type_code"),
            "unit": row.get("medicine_type_unit"),
            "description": row.get("medicine_type_description"),
        },
        "department": {
            "id": str(row["department_id"]),
            "name": row.get("department_name"),
            "code": row.get("department_code"),
        },
        "organization": {
            "id": str(row["organization_id"]),
            "name": row.get("organization_name"),
            "legal_name": row.get("organization_legal_name"),
        },
        "supplier": {
            "id": str(row["supplier_client_id"]) if row.get("supplier_client_id") is not None else None,
            "name": supplier_name,
            "email": row.get("supplier_email"),
            "phone": row.get("supplier_phone"),
        },
        "attachment": attachment_payload,
    }


def _generate_qr_png(content: str) -> bytes:
    try:
        import qrcode
    except Exception as exc:  # pragma: no cover - runtime dependency guard
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="QR generation backend is unavailable",
        ) from exc

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(content)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _build_qr_payload(
    *,
    batch_row: dict[str, Any],
    token: str,
    image_bytes: bytes,
    image_content_type: str = "image/png",
) -> dict[str, Any]:
    public_url = _build_public_url(token)
    return {
        "batch_id": str(batch_row["id"]),
        "batch_code": batch_row.get("batch_code"),
        "token": token,
        "public_url": public_url,
        "token_expires_at": batch_row.get("qr_token_expires_at"),
        "generated_at": batch_row.get("qr_generated_at"),
        "image_data_url": _encode_image_data_url(image_bytes, image_content_type),
    }


async def _get_actor_batch_or_404(
    *,
    db: Database,
    batch_id: str,
    actor: CurrentActor,
) -> dict[str, Any]:
    batch_repository = MedicineBatchRepository(db)
    batch_service = MedicineBatchService(batch_repository)
    batch = await batch_repository.get_by_id_optional(batch_id)
    if batch is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medicine batch not found")
    batch_service._ensure_actor_can_access_entity(batch, actor=actor)
    return batch


async def _get_public_batch_row(
    *,
    db: Database,
    organization_id: str,
    batch_id: str,
    token: str,
) -> dict[str, Any] | None:
    row = await db.fetchrow(
        """
        SELECT
            mb.*,
            mt.name AS medicine_type_name,
            mt.code AS medicine_type_code,
            mt.unit AS medicine_type_unit,
            mt.description AS medicine_type_description,
            d.name AS department_name,
            d.code AS department_code,
            o.name AS organization_name,
            o.legal_name AS organization_legal_name,
            c.first_name AS supplier_first_name,
            c.last_name AS supplier_last_name,
            c.company_name AS supplier_company_name,
            c.email AS supplier_email,
            c.phone AS supplier_phone
        FROM medicine_batches AS mb
        LEFT JOIN medicine_types AS mt ON mt.id = mb.medicine_type_id
        LEFT JOIN departments AS d ON d.id = mb.department_id
        LEFT JOIN organizations AS o ON o.id = mb.organization_id
        LEFT JOIN clients AS c ON c.id = mb.supplier_client_id
        WHERE mb.id = $1
          AND mb.organization_id = $2
          AND mb.qr_public_token = $3
        LIMIT 1
        """,
        batch_id,
        organization_id,
        token,
    )
    return dict(row) if row is not None else None


@router.post(
    "/batches/{batch_id}/qr",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_access("medicine_batch.write", roles=("admin", "manager")))],
)
async def generate_batch_qr(
    batch_id: str,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    settings = get_settings()
    batch = await _get_actor_batch_or_404(db=db, batch_id=batch_id, actor=current_actor)
    organization_id = str(batch["organization_id"])
    normalized_batch_id = str(batch["id"])

    token, expires_at = create_signed_token(
        subject=_build_public_subject(organization_id=organization_id, batch_id=normalized_batch_id),
        token_type=PUBLIC_MEDICINE_TOKEN_TYPE,
        secret_key=settings.auth_secret_key,
        expires_in=timedelta(days=max(1, settings.medicine_qr_token_ttl_days)),
    )
    public_url = _build_public_url(token)
    qr_image_bytes = _generate_qr_png(public_url)
    storage_key = _build_qr_storage_key(organization_id=organization_id, batch_id=normalized_batch_id)
    storage_service = get_storage_service()
    stored_qr = await storage_service.put_bytes(
        key=storage_key,
        content=qr_image_bytes,
        content_type="image/png",
    )

    now = _now_utc()
    updated_batch = await MedicineBatchRepository(db).update_by_id(
        normalized_batch_id,
        {
            "qr_public_token": token,
            "qr_token_expires_at": expires_at,
            "qr_generated_at": now,
            "qr_image_key": stored_qr.key,
            "qr_image_content_type": stored_qr.content_type,
            "qr_image_size_bytes": stored_qr.size_bytes,
        },
    )
    return _build_qr_payload(
        batch_row=updated_batch,
        token=token,
        image_bytes=qr_image_bytes,
        image_content_type=stored_qr.content_type or "image/png",
    )


@router.get(
    "/batches/{batch_id}/qr",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("medicine_batch.read", roles=("admin", "manager")))],
)
async def get_batch_qr(
    batch_id: str,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    batch = await _get_actor_batch_or_404(db=db, batch_id=batch_id, actor=current_actor)
    token = str(batch.get("qr_public_token") or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="QR code is not generated for this batch")

    qr_key = str(batch.get("qr_image_key") or "").strip()
    image_content_type = str(batch.get("qr_image_content_type") or "").strip() or "image/png"
    image_bytes: bytes | None = None
    if qr_key:
        storage_service = get_storage_service()
        qr_object = await storage_service.get_bytes(key=qr_key)
        if qr_object is not None:
            image_bytes = qr_object.content
            image_content_type = qr_object.content_type or image_content_type

    if image_bytes is None:
        image_bytes = _generate_qr_png(_build_public_url(token))

    return _build_qr_payload(
        batch_row=batch,
        token=token,
        image_bytes=image_bytes,
        image_content_type=image_content_type,
    )


@router.post(
    "/batches/{batch_id}/attachment",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_access("medicine_batch.write", roles=("admin", "manager")))],
)
async def upload_batch_attachment(
    batch_id: str,
    file: UploadFile = File(...),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    settings = get_settings()
    batch = await _get_actor_batch_or_404(db=db, batch_id=batch_id, actor=current_actor)
    organization_id = str(batch["organization_id"])
    normalized_batch_id = str(batch["id"])
    filename = _sanitize_filename(str(file.filename or ""), fallback=f"{normalized_batch_id}.bin")
    content = await file.read()
    if not content:
        raise ValidationError("Uploaded file is empty")
    if len(content) > settings.storage_max_upload_bytes:
        raise ValidationError(
            f"Uploaded file exceeds size limit ({settings.storage_max_upload_bytes} bytes)"
        )

    content_type = str(file.content_type or "").strip() or "application/octet-stream"
    storage_key = _build_attachment_storage_key(
        organization_id=organization_id,
        batch_id=normalized_batch_id,
        filename=filename,
    )
    storage_service = get_storage_service()
    previous_attachment_key = str(batch.get("attachment_key") or "").strip()
    stored_attachment = await storage_service.put_bytes(
        key=storage_key,
        content=content,
        content_type=content_type,
    )
    if previous_attachment_key and previous_attachment_key != stored_attachment.key:
        await storage_service.delete(key=previous_attachment_key)

    updated_batch = await MedicineBatchRepository(db).update_by_id(
        normalized_batch_id,
        {
            "attachment_key": stored_attachment.key,
            "attachment_name": filename,
            "attachment_content_type": stored_attachment.content_type or content_type,
            "attachment_size_bytes": stored_attachment.size_bytes,
        },
    )

    return {
        "batch_id": str(updated_batch["id"]),
        "filename": updated_batch.get("attachment_name"),
        "content_type": updated_batch.get("attachment_content_type"),
        "size_bytes": updated_batch.get("attachment_size_bytes"),
        "storage_backend": storage_service.backend_name,
    }


@router.get(
    "/public/batches/{token}",
    status_code=status.HTTP_200_OK,
)
async def get_public_batch_details(
    token: str,
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    settings = get_settings()
    try:
        claims = decode_signed_token(
            token,
            secret_key=settings.auth_secret_key,
            expected_type=PUBLIC_MEDICINE_TOKEN_TYPE,
        )
        organization_id, batch_id = _parse_public_subject(str(claims["sub"]))
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public medicine page not found") from exc

    row = await _get_public_batch_row(
        db=db,
        organization_id=organization_id,
        batch_id=batch_id,
        token=token,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public medicine page not found")

    return _build_public_batch_payload(row, token=token)


@router.get(
    "/public/batches/{token}/attachment",
    status_code=status.HTTP_200_OK,
)
async def download_public_batch_attachment(
    token: str,
    db: Database = Depends(db_dependency),
) -> Response:
    settings = get_settings()
    try:
        claims = decode_signed_token(
            token,
            secret_key=settings.auth_secret_key,
            expected_type=PUBLIC_MEDICINE_TOKEN_TYPE,
        )
        organization_id, batch_id = _parse_public_subject(str(claims["sub"]))
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found") from exc

    row = await _get_public_batch_row(
        db=db,
        organization_id=organization_id,
        batch_id=batch_id,
        token=token,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    attachment_key = str(row.get("attachment_key") or "").strip()
    if not attachment_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    storage_service = get_storage_service()
    stored_attachment = await storage_service.get_bytes(key=attachment_key)
    if stored_attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    attachment_name = _sanitize_filename(str(row.get("attachment_name") or ""), fallback="attachment")
    content_disposition = f'inline; filename="{attachment_name}"'
    return Response(
        content=stored_attachment.content,
        media_type=(stored_attachment.content_type or "application/octet-stream"),
        headers={"Content-Disposition": content_disposition},
    )


router.include_router(
    build_crud_router(
        prefix="arrivals",
        service_factory=lambda db: MedicineArrivalService(MedicineArrivalRepository(db)),
        permission_prefix="medicine_arrival",
        tags=["medicine-arrival"],
    )
)

router.include_router(
    build_crud_router(
        prefix="batches",
        service_factory=lambda db: MedicineBatchService(MedicineBatchRepository(db)),
        permission_prefix="medicine_batch",
        tags=["medicine-batch"],
    )
)

router.include_router(
    build_crud_router(
        prefix="consumptions",
        service_factory=lambda db: MedicineConsumptionService(MedicineConsumptionRepository(db)),
        permission_prefix="medicine_consumption",
        tags=["medicine-consumption"],
    )
)

router.include_router(
    build_crud_router(
        prefix="types",
        service_factory=lambda db: MedicineTypeService(MedicineTypeRepository(db)),
        permission_prefix="medicine_type",
        tags=["medicine-type"],
    )
)

register_module_stats_route(
    router,
    module="medicine",
    label="Medicine",
    tables=(
        ModuleStatsTable(key="arrivals", label="Arrivals", table="medicine_arrivals"),
        ModuleStatsTable(key="batches", label="Batches", table="medicine_batches"),
        ModuleStatsTable(key="consumptions", label="Consumptions", table="medicine_consumptions"),
        ModuleStatsTable(key="types", label="Types", table="medicine_types"),
    ),
)

__all__ = ["router"]
