from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import InvoiceState


class StateEvent(str, Enum):
    ADVANCE = "ADVANCE"
    MARK_PAID = "MARK_PAID"
    DISPUTE = "DISPUTE"
    BREATHING_SPACE = "BREATHING_SPACE"
    HANDOFF = "HANDOFF"


@dataclass(frozen=True)
class TransitionResult:
    state: InvoiceState
    reason: str


class InvoiceStateMachine:
    """Deterministic state machine for invoice progression."""

    _order = (
        InvoiceState.ISSUED,
        InvoiceState.FRIENDLY_REMINDER,
        InvoiceState.OVERDUE_CHASER,
        InvoiceState.FORMAL_NOTICE,
        InvoiceState.PRE_ACTION_PROTOCOL,
    )

    def transition(self, current: InvoiceState, event: StateEvent) -> TransitionResult:
        if event == StateEvent.MARK_PAID:
            return TransitionResult(InvoiceState.RESOLVED_PAID, "Invoice marked as paid.")
        if event == StateEvent.DISPUTE:
            return TransitionResult(InvoiceState.DISPUTED, "Debtor dispute received; automation paused.")
        if event == StateEvent.BREATHING_SPACE:
            return TransitionResult(
                InvoiceState.BREATHING_SPACE_PAUSE,
                "Breathing space notice received; automation paused.",
            )
        if event == StateEvent.HANDOFF:
            return TransitionResult(
                InvoiceState.CLIENT_HANDOFF,
                "Client handoff required by rule.",
            )
        if event != StateEvent.ADVANCE:
            raise ValueError(f"Unsupported event: {event}")

        if current in (
            InvoiceState.DISPUTED,
            InvoiceState.BREATHING_SPACE_PAUSE,
            InvoiceState.JURISDICTION_UNCERTAIN,
        ):
            return TransitionResult(current, "Paused state cannot auto-advance.")
        if current in (InvoiceState.CLIENT_HANDOFF, InvoiceState.RESOLVED_PAID):
            return TransitionResult(current, "Terminal state.")

        try:
            index = self._order.index(current)
        except ValueError as exc:
            raise ValueError(f"Unknown state: {current}") from exc

        if index == len(self._order) - 1:
            return TransitionResult(
                InvoiceState.CLIENT_HANDOFF,
                "Protocol complete; hand off to client for filing.",
            )
        return TransitionResult(self._order[index + 1], "Advanced to next workflow stage.")
