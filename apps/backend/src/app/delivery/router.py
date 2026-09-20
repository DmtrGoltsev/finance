from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.auth_context import CurrentActor
from app.config import get_settings
from app.db.models import Session as AuthSession
from app.db.session import sync_session_scope
from app.delivery.models import PushDevice

router = APIRouter(prefix="/push/devices", tags=["Push"])


class PushDeviceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=20, max_length=4096, pattern=r"^[A-Za-z0-9_:.-]+$")


def device_session() -> Iterator[Session]:
    with sync_session_scope(get_settings()) as session:
        yield session


DeviceSession = Annotated[Session, Depends(device_session)]


@router.put("/{device_id}", status_code=204, operation_id="registerPushDevice")
def register_device(
    device_id: UUID, body: PushDeviceRequest, actor: CurrentActor, session: DeviceSession
) -> Response:
    owner, sid = UUID(actor.user_id), UUID(actor.session_id or str(UUID(int=0)))
    now = datetime.now(UTC)
    # Serialize registration with logout; never register against a revoked session.
    active = session.scalar(
        select(AuthSession)
        .where(
            AuthSession.id == sid,
            AuthSession.user_id == owner,
            AuthSession.status == "active",
            AuthSession.expires_at > now,
        )
        .with_for_update()
    )
    if active is None:
        raise HTTPException(401, "authentication_required")
    device = session.get(PushDevice, device_id)
    if device is not None and device.owner_user_id != owner:
        raise HTTPException(404, "device_not_found")
    other = session.scalar(select(PushDevice).where(PushDevice.token == body.token))
    if other is not None and other.id != device_id:
        # A token is not proof of ownership; another owner must explicitly revoke it first.
        raise HTTPException(409, "token_already_registered")
    try:
        with session.begin_nested():
            if device is None:
                device = PushDevice(id=device_id, owner_user_id=owner)
                session.add(device)
            device.session_id, device.token = sid, body.token
            device.updated_at, device.revoked_at = now, None
            session.flush()
    except IntegrityError:
        raise HTTPException(409, "device_registration_conflict") from None
    return Response(status_code=204)


@router.delete("/{device_id}", status_code=204, operation_id="revokePushDevice")
def revoke_device(device_id: UUID, actor: CurrentActor, session: DeviceSession) -> Response:
    session.execute(
        update(PushDevice)
        .where(
            PushDevice.id == device_id,
            PushDevice.owner_user_id == UUID(actor.user_id),
            PushDevice.session_id == UUID(actor.session_id or str(UUID(int=0))),
        )
        .values(token=None, revoked_at=datetime.now(UTC))
    )
    return Response(status_code=204)
