"""Onboarding/implantação wizard endpoints for condominium go-live."""

import csv
import io
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.billing import Billing, BillingItem, BillingStatus
from app.models.condominium import CommissionRate, CommissionType, Condominium, OperatorAssignment
from app.models.onboarding import LegacyDebt, OnboardingImport, OnboardingStatus
from app.models.product import Product
from app.models.stock import StockAlertThreshold, StockEntry, StockEntryType
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


# ── PATCH commission ──────────────────────────────────────────────────


class PerProductRate(BaseModel):
    product_id: int
    value_per_unit: float


class CommissionRequest(BaseModel):
    commission_type: str  # fixed | percent | per_unit
    commission_value: Optional[float] = None
    per_product_rates: Optional[list[PerProductRate]] = None


@router.patch("/{condominium_id}/onboarding/commission")
async def set_commission(
    condominium_id: int,
    body: CommissionRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Configure commission type and value for a condominium during onboarding."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    try:
        ctype = CommissionType(body.commission_type)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Tipo de comissão inválido: '{body.commission_type}'")

    condo.commission_type = ctype
    condo.commission_value = Decimal(str(body.commission_value)) if body.commission_value is not None else None

    if ctype == CommissionType.per_unit and body.per_product_rates:
        today = date.today()
        for rate in body.per_product_rates:
            existing = await db.execute(
                select(CommissionRate).where(
                    CommissionRate.condominium_id == condo.id,
                    CommissionRate.product_id == rate.product_id,
                    CommissionRate.valid_from == today,
                )
            )
            cr = existing.scalar_one_or_none()
            if cr:
                cr.value_per_unit = Decimal(str(rate.value_per_unit))
            else:
                db.add(CommissionRate(
                    condominium_id=condo.id,
                    product_id=rate.product_id,
                    value_per_unit=Decimal(str(rate.value_per_unit)),
                    valid_from=today,
                ))

    await db.commit()
    return {"condominium_id": condo.id, "commission_type": ctype.value, "commission_value": float(condo.commission_value or 0)}


# ── POST generate-units ──────────────────────────────────────────────


class UnitRange(BaseModel):
    prefix: Optional[str] = ""
    start: int
    end: int


class GenerateUnitsRequest(BaseModel):
    ranges: list[UnitRange]


@router.post("/{condominium_id}/onboarding/generate-units")
async def generate_units(
    condominium_id: int,
    body: GenerateUnitsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Generate units by numeric range. Idempotent: skips existing unit codes."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    created = 0
    skipped = 0
    total_requested = 0

    for r in body.ranges:
        if r.end < r.start:
            raise HTTPException(status_code=422, detail=f"Faixa inválida: {r.start} > {r.end}")
        count = r.end - r.start + 1
        if count > 2000:
            raise HTTPException(status_code=422, detail=f"Limite de 2000 unidades por faixa excedido ({count})")
        total_requested += count

        padding = len(str(r.end))
        prefix = r.prefix or ""

        for n in range(r.start, r.end + 1):
            code = f"{prefix}{str(n).zfill(padding)}"
            if len(code) > 20:
                raise HTTPException(status_code=422, detail=f"Código de unidade muito longo: '{code}' (máx 20 caracteres)")
            existing = await db.execute(
                select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == code)
            )
            if existing.scalar_one_or_none():
                skipped += 1
                continue
            db.add(Unit(condominium_id=condo.id, unit_code=code, unit_prefix=prefix, unit_number=n, is_active=True))
            created += 1

    await db.flush()

    # Count total units
    total_result = await db.execute(
        select(func.count(Unit.id)).where(Unit.condominium_id == condo.id, Unit.is_active.is_(True))
    )
    total_units = total_result.scalar() or 0

    await db.commit()
    return {"created": created, "skipped": skipped, "total_units": total_units}


# ── POST generate-units-by-floor ─────────────────────────────────────


class FloorBlock(BaseModel):
    prefix: Optional[str] = ""
    floor_start: int  # label do primeiro andar (ex: 1 ou 10)
    floor_end: int    # label do último andar (ex: 9 ou 20)
    apts_per_floor: int


class GenerateUnitsByFloorRequest(BaseModel):
    blocks: list[FloorBlock]
    clear_before: bool = False  # se True, apaga todas as unidades sem moradores antes de gerar


@router.post("/{condominium_id}/onboarding/generate-units-by-floor")
async def generate_units_by_floor(
    condominium_id: int,
    body: GenerateUnitsByFloorRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Generate units using Brazilian floor numbering (floor_label × 100 + apt).
    Supports multiple blocks/towers with different floor ranges.
    clear_before=True removes all units without residents before generating."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    if body.clear_before:
        # Remove only units that have no residents linked (safe delete)
        units_with_residents = select(Resident.unit_id).where(Resident.unit_id.isnot(None)).scalar_subquery()
        await db.execute(
            delete(Unit).where(
                Unit.condominium_id == condo.id,
                Unit.id.notin_(units_with_residents),
            )
        )

    created = 0
    skipped = 0

    for block in body.blocks:
        if block.floor_end < block.floor_start:
            raise HTTPException(
                status_code=422,
                detail=f"Andar inválido: primeiro ({block.floor_start}) > último ({block.floor_end})",
            )
        if not (1 <= block.apts_per_floor <= 99):
            raise HTTPException(status_code=422, detail="Apartamentos por andar deve ser entre 1 e 99")

        num_floors = block.floor_end - block.floor_start + 1
        total_block = num_floors * block.apts_per_floor
        if total_block > 2000:
            raise HTTPException(
                status_code=422,
                detail=f"Bloco excede o limite de 2000 unidades ({total_block}). Divida em múltiplos blocos.",
            )

        prefix = block.prefix or ""
        for floor in range(block.floor_start, block.floor_end + 1):
            for apt in range(1, block.apts_per_floor + 1):
                unit_num = floor * 100 + apt
                code = f"{prefix}{unit_num}"
                if len(code) > 20:
                    raise HTTPException(status_code=422, detail=f"Código muito longo: '{code}' (máx 20 caracteres)")
                existing = await db.execute(
                    select(Unit).where(Unit.condominium_id == condo.id, Unit.unit_code == code)
                )
                if existing.scalar_one_or_none():
                    skipped += 1
                    continue
                db.add(Unit(condominium_id=condo.id, unit_code=code, unit_prefix=prefix, unit_number=unit_num, is_active=True))
                created += 1

    await db.flush()
    total_result = await db.execute(
        select(func.count(Unit.id)).where(Unit.condominium_id == condo.id, Unit.is_active.is_(True))
    )
    total_units = total_result.scalar() or 0
    await db.commit()
    return {"created": created, "skipped": skipped, "total_units": total_units}


# ── GET onboarding status ────────────────────────────────────────────


class RequirementItem(BaseModel):
    key: str
    met: bool
    message: str


class OnboardingStatusResponse(BaseModel):
    requirements: list[RequirementItem]
    can_complete: bool


@router.get("/{condominium_id}/onboarding/status")
async def get_onboarding_status(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return checklist of onboarding requirements and whether completion is allowed."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    requirements: list[RequirementItem] = []

    # 1. Units
    units_result = await db.execute(
        select(func.count(Unit.id)).where(Unit.condominium_id == condo.id, Unit.is_active.is_(True))
    )
    units_count = units_result.scalar() or 0
    requirements.append(RequirementItem(
        key="units",
        met=units_count > 0,
        message=f"{units_count} unidade(s) cadastrada(s)" if units_count > 0 else "Nenhuma unidade cadastrada",
    ))

    # 2. Operator
    op_result = await db.execute(
        select(func.count(OperatorAssignment.id)).where(OperatorAssignment.condominium_id == condo.id)
    )
    op_count = op_result.scalar() or 0
    requirements.append(RequirementItem(
        key="operator",
        met=op_count > 0,
        message="Operador atribuído" if op_count > 0 else "Nenhum operador atribuído",
    ))

    # 3. Commission
    commission_ok = False
    if condo.commission_type == CommissionType.per_unit:
        cr_result = await db.execute(
            select(func.count(CommissionRate.id)).where(CommissionRate.condominium_id == condo.id)
        )
        commission_ok = (cr_result.scalar() or 0) > 0
    else:
        commission_ok = condo.commission_value is not None
    requirements.append(RequirementItem(
        key="commission",
        met=commission_ok,
        message="Comissão configurada" if commission_ok else "Comissão não configurada",
    ))

    can_complete = all(r.met for r in requirements)
    return OnboardingStatusResponse(requirements=requirements, can_complete=can_complete)


# ── POST reopen ──────────────────────────────────────────────────────


@router.post("/{condominium_id}/onboarding/reopen")
async def reopen_onboarding(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Reopen onboarding for a condominium that was previously completed."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")
    if not condo.onboarding_complete:
        raise HTTPException(status_code=422, detail="Condomínio ainda não foi ativado")

    condo.onboarding_complete = False
    await db.commit()
    return {"condominium_id": condo.id, "name": condo.name, "onboarding_complete": False}


# ── GET existing units ───────────────────────────────────────────────


@router.get("/{condominium_id}/onboarding/units")
async def list_onboarding_units(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """List existing units for this condominium (used in wizard step 2)."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    result = await db.execute(
        select(Unit).where(Unit.condominium_id == condo.id, Unit.is_active.is_(True)).order_by(Unit.unit_prefix, Unit.unit_number, Unit.unit_code)
    )
    units = result.scalars().all()
    return {"units": [{"id": u.id, "unit_code": u.unit_code} for u in units], "total": len(units)}


# ── POST stock-alerts ────────────────────────────────────────────────


class StockAlertItem(BaseModel):
    product_id: int
    min_quantity: int


class StockAlertsRequest(BaseModel):
    global_min: Optional[int] = None
    items: Optional[list[StockAlertItem]] = None


@router.post("/{condominium_id}/onboarding/stock-alerts")
async def set_stock_alerts(
    condominium_id: int,
    body: StockAlertsRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Configure minimum stock alert thresholds. Supports global and per-product."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    saved = 0

    # Global threshold (product_id=NULL)
    if body.global_min is not None:
        existing = await db.execute(
            select(StockAlertThreshold).where(
                StockAlertThreshold.condominium_id == condo.id,
                StockAlertThreshold.product_id.is_(None),
            )
        )
        threshold = existing.scalar_one_or_none()
        if threshold:
            threshold.min_quantity = body.global_min
        else:
            db.add(StockAlertThreshold(condominium_id=condo.id, product_id=None, min_quantity=body.global_min))
        saved += 1

    # Per-product thresholds
    if body.items:
        for item in body.items:
            existing = await db.execute(
                select(StockAlertThreshold).where(
                    StockAlertThreshold.condominium_id == condo.id,
                    StockAlertThreshold.product_id == item.product_id,
                )
            )
            threshold = existing.scalar_one_or_none()
            if threshold:
                threshold.min_quantity = item.min_quantity
            else:
                db.add(StockAlertThreshold(
                    condominium_id=condo.id,
                    product_id=item.product_id,
                    min_quantity=item.min_quantity,
                ))
            saved += 1

    await db.commit()
    return {"saved": saved}


@router.get("/{condominium_id}/onboarding/stock-alerts")
async def get_stock_alerts(
    condominium_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return saved stock alert thresholds for a condominium."""
    result = await db.execute(
        select(StockAlertThreshold).where(StockAlertThreshold.condominium_id == condominium_id)
    )
    thresholds = result.scalars().all()
    global_min = None
    items = []
    for t in thresholds:
        if t.product_id is None:
            global_min = t.min_quantity
        else:
            items.append({"product_id": t.product_id, "min_quantity": t.min_quantity})
    return {"global_min": global_min, "items": items}


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
    """Mark condominium as fully onboarded. Validates mandatory requirements first."""
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    # Validate mandatory requirements
    unmet: list[str] = []

    units_result = await db.execute(
        select(func.count(Unit.id)).where(Unit.condominium_id == condo.id, Unit.is_active.is_(True))
    )
    if (units_result.scalar() or 0) == 0:
        unmet.append("Nenhuma unidade cadastrada — volte à Etapa 2")

    op_result = await db.execute(
        select(func.count(OperatorAssignment.id)).where(OperatorAssignment.condominium_id == condo.id)
    )
    if (op_result.scalar() or 0) == 0:
        unmet.append("Nenhum operador atribuído — volte à Etapa 1")

    if condo.commission_type == CommissionType.per_unit:
        cr_result = await db.execute(
            select(func.count(CommissionRate.id)).where(CommissionRate.condominium_id == condo.id)
        )
        if (cr_result.scalar() or 0) == 0:
            unmet.append("Comissão por unidade/produto sem taxas configuradas — volte à Etapa 1")
    elif condo.commission_value is None:
        unmet.append("Comissão não configurada — volte à Etapa 1")

    if unmet:
        raise HTTPException(status_code=422, detail={"message": "Requisitos não atendidos", "unmet": unmet})

    condo.onboarding_complete = True
    if body.go_live_date:
        condo.go_live_date = date.fromisoformat(body.go_live_date)

    await db.commit()
    return {"condominium_id": condo.id, "name": condo.name, "onboarding_complete": True}
