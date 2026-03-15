"""Resident management endpoints.

Handles bulk import and individual updates of resident data.
Accessible to assigned operators (not admin-only) since operators
manage their own condominium's resident records day-to-day.
"""

import csv
import io
import re
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_operator
from app.models.condominium import Condominium, OperatorAssignment
from app.models.unit import Resident, Unit
from app.models.user import User, UserRole

router = APIRouter(prefix="/condominiums", tags=["residents"])


# ── Validation helpers ────────────────────────────────────────────────


def _is_masked_cpf(cpf: str) -> bool:
    """Return True if the CPF is already masked (e.g. ***.***.***.XX from ERP)."""
    return "*" in cpf


def _validate_cpf(cpf: str) -> bool:
    """Validate Brazilian CPF check digits. Returns True if valid."""
    digits = re.sub(r"[^\d]", "", cpf)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    # First check digit
    s1 = sum(int(digits[i]) * (10 - i) for i in range(9))
    d1 = 11 - (s1 % 11)
    if d1 >= 10:
        d1 = 0
    # Second check digit
    s2 = sum(int(digits[i]) * (11 - i) for i in range(10))
    d2 = 11 - (s2 % 11)
    if d2 >= 10:
        d2 = 0
    return int(digits[9]) == d1 and int(digits[10]) == d2


def _validate_phone(phone: str) -> bool:
    """Validate Brazilian phone: must have 10 or 11 digits after stripping formatting."""
    digits = re.sub(r"[^\d]", "", phone)
    return len(digits) in (10, 11)


def _normalize_key(h: str) -> str:
    h = h.strip().lower()
    for src, dst in [
        ("ã", "a"), ("â", "a"), ("á", "a"), ("à", "a"),
        ("ç", "c"), ("é", "e"), ("ê", "e"), ("í", "i"),
        ("ó", "o"), ("ô", "o"), ("ú", "u"), (" ", "_"),
    ]:
        h = h.replace(src, dst)
    return h


async def _read_rows(file: UploadFile) -> list[dict]:
    content = await file.read()
    filename = (file.filename or "").lower()
    if filename.endswith(".xlsx"):
        try:
            import openpyxl  # noqa: PLC0415
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                return []
            headers = [_normalize_key(str(h or "")) for h in rows[0]]
            return [
                {headers[i]: (str(v).strip() if v is not None else "") for i, v in enumerate(row)}
                for row in rows[1:]
                if any(v is not None for v in row)
            ]
        except ImportError:
            raise HTTPException(status_code=422, detail="Suporte a XLSX requer openpyxl instalado. Use CSV.")
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    return [{_normalize_key(k): (v or "").strip() for k, v in row.items()} for row in reader]


async def _check_assignment(condominium_id: int, user: User, db: AsyncSession) -> None:
    """Verify operator is assigned to the condominium (admins bypass this check)."""
    if user.role == UserRole.admin:
        return
    result = await db.execute(
        select(OperatorAssignment).where(
            OperatorAssignment.condominium_id == condominium_id,
            OperatorAssignment.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Você não está atribuído a este condomínio.")


# ── POST import-residents ─────────────────────────────────────────────


@router.post("/{condominium_id}/residents/import")
async def import_residents(
    condominium_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Import or update residents from CSV/XLSX.

    Accessible to assigned operators (and admins).
    Validates CPF and phone format. Returns per-row results with warnings.
    Columns: unidade, nome, cpf, telefone
    """
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    await _check_assignment(condominium_id, current_user, db)

    rows = await _read_rows(file)
    imported = 0
    warnings: list[dict] = []
    errors: list[dict] = []

    for i, row in enumerate(rows, 2):
        unit_code = row.get("unidade", "").strip()
        if not unit_code:
            errors.append({"row": i, "unit": "", "error": "Campo 'unidade' obrigatório"})
            continue

        # Unit must already exist — operators don't create units
        ur = await db.execute(
            select(Unit).where(Unit.condominium_id == condominium_id, Unit.unit_code == unit_code)
        )
        unit = ur.scalar_one_or_none()
        if not unit:
            errors.append({"row": i, "unit": unit_code, "error": f"Unidade '{unit_code}' não encontrada. Cadastre as unidades primeiro (Etapa 2 da implantação)."})
            continue

        name = row.get("nome", "").strip() or None
        cpf = row.get("cpf", "").strip() or None
        phone = row.get("telefone", row.get("tel", row.get("fone", ""))).strip() or None

        # ── Validation ──────────────────────────────────────────
        row_warnings: list[str] = []

        if cpf and not _is_masked_cpf(cpf):
            if not _validate_cpf(cpf):
                row_warnings.append(f"CPF inválido: '{cpf}'")

        if phone and not _validate_phone(phone):
            row_warnings.append(f"Telefone inválido: '{phone}' (esperado: 10 ou 11 dígitos)")

        if row_warnings:
            warnings.append({"row": i, "unit": unit_code, "name": name or "", "warnings": row_warnings})

        # ── Upsert Resident ──────────────────────────────────────
        rr = await db.execute(
            select(Resident).where(Resident.unit_id == unit.id, Resident.is_current.is_(True))
        )
        resident = rr.scalar_one_or_none()

        if resident:
            if name:
                resident.name = name
            if cpf:
                resident.cpf_masked = cpf
            if phone:
                resident.phone = phone
        else:
            db.add(Resident(
                unit_id=unit.id,
                name=name,
                cpf_masked=cpf,
                phone=phone,
                is_current=True,
            ))

        imported += 1

    await db.commit()
    return {
        "imported": imported,
        "warnings_count": len(warnings),
        "errors_count": len(errors),
        "warnings": warnings,
        "errors": errors,
    }
