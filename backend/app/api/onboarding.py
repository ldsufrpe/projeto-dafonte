"""Onboarding/implantação wizard endpoints for condominium go-live."""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import Condominium
from app.models.onboarding import LegacyDebt, OnboardingImport, OnboardingStatus
from app.models.product import Product
from app.models.stock import StockEntry, StockEntryType
from app.models.unit import Resident, Unit
from app.models.user import User

router = APIRouter(prefix="/condominiums", tags=["onboarding"])


def _normalize_key(h: str) -> str:
    h = h.strip().lower()
    for src, dst in [("ã","a"),("â","a"),("á","a"),("à","a"),("ç","c"),("é","e"),("ê","e"),("í","i"),("ó","o"),("ô","o"),("ú","u"),(" ","_")]:
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


# ── POST import-residents ─────────────────────────────────────────────


@router.post("/{condominium_id}/onboarding/import-residents")
async def import_residents(
    condominium_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Import residents from CSV/XLSX. Columns: unidade, nome, cpf, telefone."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    rows = await _read_rows(file)
    imported = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, 2):
        unit_code = row.get("unidade", "").strip()
        if not unit_code:
            errors.append({"row": i, "error": "Campo 'unidade' obrigatório"})
            continue

        ur = await db.execute(
            select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == unit_code)
        )
        unit = ur.scalar_one_or_none()
        if not unit:
            unit = Unit(condominium_id=condo.id, unit_code=unit_code, is_active=True)
            db.add(unit)
            await db.flush()

        rr = await db.execute(
            select(Resident).where(Resident.unit_id == unit.id, Resident.is_current.is_(True))
        )
        resident = rr.scalar_one_or_none()
        name = row.get("nome", "").strip() or None
        cpf = row.get("cpf", "").strip() or None
        phone = row.get("telefone", "").strip() or None

        if resident:
            if name:
                resident.name = name
            if cpf:
                resident.cpf_masked = cpf
            if phone:
                resident.phone = phone
        else:
            db.add(Resident(unit_id=unit.id, name=name, cpf_masked=cpf, phone=phone, is_current=True))

        imported += 1

    db.add(OnboardingImport(
        condominium_id=condo.id,
        source_filename=file.filename or "upload",
        status=OnboardingStatus.error if errors else OnboardingStatus.done,
        row_count=imported,
        error_log={"errors": errors} if errors else None,
    ))
    await db.commit()
    return {"imported": imported, "errors_count": len(errors), "errors": errors}


# ── POST stock-opening ────────────────────────────────────────────────


class StockItem(BaseModel):
    product_id: int
    quantity: int


class StockOpeningRequest(BaseModel):
    reference_month: str
    items: list[StockItem]
    notes: Optional[str] = None


@router.post("/{condominium_id}/onboarding/stock-opening")
async def stock_opening(
    condominium_id: int,
    body: StockOpeningRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Set initial stock balance. One initial entry per product per month."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    created = 0
    for item in body.items:
        ex = await db.execute(
            select(StockEntry).where(
                StockEntry.condominium_id == condo.id,
                StockEntry.product_id == item.product_id,
                StockEntry.reference_month == body.reference_month,
                StockEntry.entry_type == StockEntryType.initial,
            )
        )
        if ex.scalar_one_or_none():
            continue
        db.add(StockEntry(
            condominium_id=condo.id,
            product_id=item.product_id,
            reference_month=body.reference_month,
            quantity=item.quantity,
            entry_type=StockEntryType.initial,
            notes=body.notes,
        ))
        created += 1

    await db.commit()
    return {"created": created, "reference_month": body.reference_month}


# ── POST legacy-debts ─────────────────────────────────────────────────


@router.post("/{condominium_id}/onboarding/legacy-debts")
async def import_legacy_debts(
    condominium_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Import legacy debts. Columns: unidade, mes_referencia, valor, descricao."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    rows = await _read_rows(file)
    imported = 0
    errors: list[dict] = []

    for i, row in enumerate(rows, 2):
        unit_code = row.get("unidade", "").strip()
        mes = row.get("mes_referencia", row.get("mes", "")).strip()
        valor_str = row.get("valor", "").strip().replace(",", ".")
        desc = row.get("descricao", "").strip() or None

        if not unit_code or not mes or not valor_str:
            errors.append({"row": i, "error": "Campos obrigatórios: unidade, mes_referencia, valor"})
            continue

        try:
            amount = Decimal(valor_str)
        except InvalidOperation:
            errors.append({"row": i, "error": f"Valor inválido: '{valor_str}'"})
            continue

        ur = await db.execute(
            select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == unit_code)
        )
        unit = ur.scalar_one_or_none()
        if not unit:
            errors.append({"row": i, "error": f"Unidade '{unit_code}' não encontrada. Importe moradores primeiro."})
            continue

        db.add(LegacyDebt(unit_id=unit.id, reference_month=mes, amount=amount, description=desc))
        imported += 1

    db.add(OnboardingImport(
        condominium_id=condo.id,
        source_filename=file.filename or "upload",
        status=OnboardingStatus.error if errors else OnboardingStatus.done,
        row_count=imported,
        error_log={"errors": errors} if errors else None,
    ))
    await db.commit()
    return {"imported": imported, "errors_count": len(errors), "errors": errors}


# ── POST import-history ───────────────────────────────────────────────


@router.post("/{condominium_id}/onboarding/import-history")
async def import_history(
    condominium_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Import historical billing. Columns: unidade, mes_referencia, produto, quantidade, preco_unitario, status_pgto."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    prod_result = await db.execute(select(Product))
    product_map: dict[str, Product] = {p.name.lower(): p for p in prod_result.scalars().all()}

    rows = await _read_rows(file)
    imported_billings = 0
    imported_items = 0
    errors: list[dict] = []

    status_map = {
        "pago": BillingStatus.paid, "paid": BillingStatus.paid,
        "em aberto": BillingStatus.open, "open": BillingStatus.open,
        "sem consumo": BillingStatus.no_consumption,
    }

    for i, row in enumerate(rows, 2):
        unit_code = row.get("unidade", "").strip()
        mes = row.get("mes_referencia", row.get("mes", "")).strip()
        produto_nome = row.get("produto", "").strip().lower()
        qty_str = row.get("quantidade", "0").strip()
        preco_str = row.get("preco_unitario", "0").strip().replace(",", ".")
        status_str = row.get("status_pgto", "pago").strip().lower()

        if not unit_code or not mes or not produto_nome:
            errors.append({"row": i, "error": "Campos obrigatórios: unidade, mes_referencia, produto"})
            continue

        product = product_map.get(produto_nome)
        if not product:
            errors.append({"row": i, "error": f"Produto '{produto_nome}' não encontrado no catálogo"})
            continue

        try:
            qty = int(qty_str)
            price = Decimal(preco_str)
        except (ValueError, InvalidOperation):
            errors.append({"row": i, "error": f"Quantidade ou preço inválido na linha {i}"})
            continue

        ur = await db.execute(
            select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == unit_code)
        )
        unit = ur.scalar_one_or_none()
        if not unit:
            unit = Unit(condominium_id=condo.id, unit_code=unit_code, is_active=True)
            db.add(unit)
            await db.flush()

        br = await db.execute(
            select(Billing).where(Billing.unit_id == unit.id, Billing.reference_month == mes)
        )
        billing = br.scalar_one_or_none()
        billing_status = status_map.get(status_str, BillingStatus.paid)

        if not billing:
            billing = Billing(
                unit_id=unit.id,
                reference_month=mes,
                status=billing_status,
                is_legacy=True,
                total_amount=Decimal("0"),
            )
            db.add(billing)
            await db.flush()
            imported_billings += 1
        else:
            billing.status = billing_status

        ex_item = await db.execute(
            select(BillingItem).where(
                BillingItem.billing_id == billing.id, BillingItem.product_id == product.id
            )
        )
        bi = ex_item.scalar_one_or_none()
        line_total = Decimal(str(qty)) * price
        if bi:
            bi.quantity = qty
            bi.unit_price_snapshot = price
            bi.line_total = line_total
        else:
            db.add(BillingItem(
                billing_id=billing.id,
                product_id=product.id,
                quantity=qty,
                unit_price_snapshot=price,
                line_total=line_total,
            ))
            imported_items += 1

        all_items = await db.execute(select(BillingItem).where(BillingItem.billing_id == billing.id))
        billing.total_amount = sum(item.line_total for item in all_items.scalars().all())

    db.add(OnboardingImport(
        condominium_id=condo.id,
        source_filename=file.filename or "upload",
        status=OnboardingStatus.error if errors else OnboardingStatus.done,
        row_count=imported_items,
        error_log={"errors": errors} if errors else None,
    ))
    await db.commit()
    return {"imported_billings": imported_billings, "imported_items": imported_items, "errors_count": len(errors), "errors": errors}


# ── POST complete ─────────────────────────────────────────────────────


class CompleteRequest(BaseModel):
    go_live_date: Optional[str] = None  # YYYY-MM-DD


@router.post("/{condominium_id}/onboarding/complete")
async def complete_onboarding(
    condominium_id: int,
    body: CompleteRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Mark condominium as fully onboarded."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    condo.onboarding_complete = True
    if body.go_live_date:
        condo.go_live_date = date.fromisoformat(body.go_live_date)

    await db.commit()
    return {"condominium_id": condo.id, "name": condo.name, "onboarding_complete": True}
