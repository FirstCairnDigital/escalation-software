from __future__ import annotations

from contextvars import ContextVar


current_client_id: ContextVar[str] = ContextVar("current_client_id", default="DEFAULT_CLIENT")
current_role: ContextVar[str] = ContextVar("current_role", default="admin")
current_identity: ContextVar[str] = ContextVar("current_identity", default="anonymous")


def set_request_context(*, client_id: str, role: str, identity: str) -> tuple[object, object, object]:
    client_token = current_client_id.set(client_id)
    role_token = current_role.set(role)
    identity_token = current_identity.set(identity)
    return client_token, role_token, identity_token


def reset_request_context(tokens: tuple[object, object, object]) -> None:
    client_token, role_token, identity_token = tokens
    current_client_id.reset(client_token)
    current_role.reset(role_token)
    current_identity.reset(identity_token)
