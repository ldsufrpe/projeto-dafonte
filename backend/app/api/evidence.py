"""Evidence upload — image capture as proof of delivery."""

import os
import uuid
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.billing import Billing
from app.models.condominium import OperatorAssignment
from app.models.evidence import Evidence
from app.models.unit import Unit
from app.models.user import User, UserRole
from app.schemas.evidence import EvidenceOut

router = APIRouter(prefix="/condominiums", tags=["evidências"])

EVIDENCE_ROOT = "/evidencias"
MAX_WIDTH = 1280
WEBP_QUALITY = 85
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30 MB — covers flagship smartphone cameras


def _process_image(raw_bytes: bytes) -> bytes:
    """Resize to max 1280px width and convert to WebP."""
    img = Image.open(BytesIO(raw_bytes))

    # Handle EXIF orientation
    try:
        from PIL import ExifTags
        for orientation_key in ExifTags.TAGS.keys():
            if ExifTags.TAGS[orientation_key] == "Orientation":
                break
        exif = img._getexif()
        if exif and orientation_key in exif:
            orientation = exif[orientation_key]
            if orientation == 3:
                img = img.rotate(180, expand=True)
            elif orientation == 6:
                img = img.rotate(270, expand=True)
            elif orientation == 8:
                img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, TypeError):
        pass

    # Convert RGBA → RGB for WebP
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    # Resize if wider than MAX_WIDTH
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        new_height = int(img.height * ratio)
        img = img.resize((MAX_WIDTH, new_height), Image.LANCZOS)

    # Save as WebP
    buffer = BytesIO()
    img.save(buffer, format="WEBP", quality=WEBP_QUALITY)
    return buffer.getvalue()


def _build_url(file_path: str) -> str:
    return f"/media/evidencias/{file_path}"


@router.post("/{condominium_id}/evidencias", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
async def upload_evidence(
    condominium_id: int,
    billing_id: int = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate MIME type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Tipo de arquivo não aceito: {file.content_type}. Envie apenas imagens (JPEG, PNG, HEIC, etc.).",
        )

    # Operator assignment check
    if current_user.role == UserRole.operator:
        asgn = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.condominium_id == condominium_id,
                OperatorAssignment.user_id == current_user.id,
            )
        )
        if not asgn.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este condomínio")

    # Validate billing belongs to the condominium
    billing = await db.get(Billing, billing_id)
    if not billing:
        raise HTTPException(status_code=404, detail="Lançamento não encontrado")

    unit = await db.get(Unit, billing.unit_id)
    if not unit or unit.condominium_id != condominium_id:
        raise HTTPException(status_code=400, detail="Lançamento não pertence a este condomínio")

    # Read and enforce size limit
    raw_bytes = await file.read()
    if len(raw_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo muito grande ({len(raw_bytes) // (1024*1024)} MB). Limite: {MAX_FILE_SIZE // (1024*1024)} MB.",
        )

    webp_bytes = _process_image(raw_bytes)

    # Build path: {year}/{month}/{condo_id}/{uuid}.webp
    now = datetime.now()
    relative_dir = f"{now.year}/{now.month:02d}/{condominium_id}"
    file_name = f"{uuid.uuid4().hex}.webp"
    relative_path = f"{relative_dir}/{file_name}"
    absolute_dir = os.path.join(EVIDENCE_ROOT, relative_dir)

    os.makedirs(absolute_dir, exist_ok=True)
    absolute_path = os.path.join(absolute_dir, file_name)

    with open(absolute_path, "wb") as f:
        f.write(webp_bytes)

    # Persist record — clean up file if DB commit fails
    evidence = Evidence(
        billing_id=billing_id,
        file_path=relative_path,
        original_filename=file.filename or "upload.jpg",
    )
    db.add(evidence)
    try:
        await db.commit()
    except Exception:
        if os.path.exists(absolute_path):
            os.remove(absolute_path)
        raise HTTPException(status_code=500, detail="Erro ao salvar evidência. Tente novamente.")
    await db.refresh(evidence)

    return EvidenceOut(
        id=evidence.id,
        billing_id=evidence.billing_id,
        original_filename=evidence.original_filename,
        file_url=_build_url(relative_path),
        uploaded_at=evidence.uploaded_at,
    )


@router.get("/{condominium_id}/evidencias/{billing_id}", response_model=list[EvidenceOut])
async def list_evidences(
    condominium_id: int,
    billing_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Operator assignment check
    if current_user.role == UserRole.operator:
        asgn = await db.execute(
            select(OperatorAssignment).where(
                OperatorAssignment.condominium_id == condominium_id,
                OperatorAssignment.user_id == current_user.id,
            )
        )
        if not asgn.scalar_one_or_none():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sem acesso a este condomínio")

    result = await db.execute(
        select(Evidence)
        .where(Evidence.billing_id == billing_id)
        .order_by(Evidence.uploaded_at.desc())
    )
    evidences = result.scalars().all()
    return [
        EvidenceOut(
            id=e.id,
            billing_id=e.billing_id,
            original_filename=e.original_filename,
            file_url=_build_url(e.file_path),
            uploaded_at=e.uploaded_at,
        )
        for e in evidences
    ]


@router.delete("/{condominium_id}/evidencias/{evidence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidence(
    condominium_id: int,
    evidence_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    evidence = await db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidência não encontrada")

    # Delete file from disk
    absolute_path = os.path.join(EVIDENCE_ROOT, evidence.file_path)
    if os.path.exists(absolute_path):
        os.remove(absolute_path)

    await db.delete(evidence)
    await db.commit()
