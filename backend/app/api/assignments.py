"""Operator ↔ Condominium assignment management (admin only)."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_admin
from app.models.condominium import Condominium, OperatorAssignment
from app.models.user import User, UserRole
from app.schemas.assignment import AssignRequest, AssignmentOut, OperatorOut

router = APIRouter(prefix="/assignments", tags=["assignments"])


async def _build_operator_out(db: AsyncSession, user: User) -> OperatorOut:
    result = await db.execute(
        select(OperatorAssignment.condominium_id).where(OperatorAssignment.user_id == user.id)
    )
    condo_ids = list(result.scalars().all())
    return OperatorOut(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        condominium_ids=condo_ids,
    )


@router.get("/operators", response_model=list[OperatorOut])
async def list_operators(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Return all operator users with their assigned condominium ids."""
    result = await db.execute(
        select(User).where(User.role == UserRole.operator).order_by(User.full_name, User.username)
    )
    users = result.scalars().all()
    return [await _build_operator_out(db, u) for u in users]


@router.post("/condominiums/{condominium_id}", response_model=AssignmentOut)
async def assign_operator(
    condominium_id: int,
    body: AssignRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Assign, reassign, or remove the operator for a condominium.

    - user_id = <int>  → assign (replaces existing assignment if any)
    - user_id = null   → remove current assignment
    """
    # Ensure condominium exists
    condo = await db.get(Condominium, condominium_id)
    if not condo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Condomínio não encontrado")

    # Remove existing assignment (if any)
    existing = await db.execute(
        select(OperatorAssignment).where(OperatorAssignment.condominium_id == condominium_id)
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row:
        await db.delete(existing_row)

    if body.user_id is None:
        # Just remove — no new assignment
        await db.commit()
        return AssignmentOut(condominium_id=condominium_id, operator=None)

    # Validate target user is an operator
    user = await db.get(User, body.user_id)
    if not user or user.role != UserRole.operator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Usuário não encontrado ou não é operador",
        )

    db.add(OperatorAssignment(user_id=user.id, condominium_id=condominium_id))
    await db.commit()

    return AssignmentOut(
        condominium_id=condominium_id,
        operator=await _build_operator_out(db, user),
    )
