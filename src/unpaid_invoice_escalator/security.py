from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from time import monotonic


ROLE_RANK = {
    "viewer": 1,
    "operator": 2,
    "admin": 3,
}


@dataclass(frozen=True)
class RequestDecision:
    allowed: bool
    status_code: int | None = None
    detail: str | None = None
    identity: str = "anonymous"


class ApiSecurityController:
    def __init__(
        self,
        *,
        enabled: bool,
        api_keys: dict[str, str],
        rate_limit_per_minute: int,
        auth_failure_alert_threshold: int = 10,
        rate_limit_alert_threshold: int = 10,
        server_error_alert_threshold: int = 5,
        audit_log_limit: int = 200,
    ) -> None:
        self.enabled = enabled
        self.api_keys = api_keys
        self.rate_limit_per_minute = rate_limit_per_minute
        self.auth_failure_alert_threshold = auth_failure_alert_threshold
        self.rate_limit_alert_threshold = rate_limit_alert_threshold
        self.server_error_alert_threshold = server_error_alert_threshold
        self._request_timestamps: dict[str, deque[float]] = {}
        self._request_count = 0
        self._status_counts: dict[str, int] = {}
        self._rate_limited_count = 0
        self._auth_fail_count = 0
        self._forbidden_count = 0
        self._server_error_count = 0
        self._upload_rejected_count = 0
        self._upload_quarantined_count = 0
        self._upload_rejections_by_reason: dict[str, int] = {}
        self._audit_events: deque[dict[str, object]] = deque(maxlen=max(1, audit_log_limit))
        self._last_alert: str | None = None
        self._active_alerts: set[str] = set()

    def is_public_path(self, path: str) -> bool:
        return path in ("/health", "/ready")

    def _required_role(self, *, method: str, path: str) -> str:
        if path == "/metrics" or path.startswith("/deployment/"):
            return "admin"
        if method.upper() == "GET":
            return "viewer"
        return "operator"

    def _role_allows(self, *, actual: str, required: str) -> bool:
        return ROLE_RANK.get(actual, 0) >= ROLE_RANK.get(required, 99)

    def evaluate_request(
        self,
        *,
        method: str,
        path: str,
        api_key: str | None,
        client_host: str | None,
    ) -> RequestDecision:
        identity = api_key or client_host or "anonymous"
        if self.is_public_path(path):
            return RequestDecision(allowed=True, identity=identity)
        if not self.enabled:
            return RequestDecision(allowed=True, identity=identity)

        role = self.api_keys.get(api_key or "")
        if role is None:
            self._auth_fail_count += 1
            self._record_audit_event(
                event_type="AUTH_FAILURE",
                severity="WARN",
                method=method,
                path=path,
                identity=identity,
                detail="Missing or invalid API key.",
            )
            self._trigger_threshold_alert(
                metric_name="auth_failures_total",
                count=self._auth_fail_count,
                threshold=self.auth_failure_alert_threshold,
                detail="Authentication failure threshold reached.",
            )
            return RequestDecision(allowed=False, status_code=401, detail="Missing or invalid API key.", identity=identity)

        required_role = self._required_role(method=method, path=path)
        if not self._role_allows(actual=role, required=required_role):
            self._forbidden_count += 1
            self._record_audit_event(
                event_type="RBAC_FORBIDDEN",
                severity="WARN",
                method=method,
                path=path,
                identity=identity,
                detail=f"Role '{role}' lacks permission for required role '{required_role}'.",
            )
            return RequestDecision(
                allowed=False,
                status_code=403,
                detail=f"Insufficient role. Required: {required_role}.",
                identity=identity,
            )
        return RequestDecision(allowed=True, identity=identity)

    def check_rate_limit(self, identity: str) -> RequestDecision:
        now = monotonic()
        window_start = now - 60.0
        entries = self._request_timestamps.setdefault(identity, deque())
        while entries and entries[0] < window_start:
            entries.popleft()
        if len(entries) >= self.rate_limit_per_minute:
            self._rate_limited_count += 1
            self._record_audit_event(
                event_type="RATE_LIMIT_EXCEEDED",
                severity="WARN",
                method=None,
                path=None,
                identity=identity,
                detail="Rate limit exceeded.",
            )
            self._trigger_threshold_alert(
                metric_name="rate_limited_total",
                count=self._rate_limited_count,
                threshold=self.rate_limit_alert_threshold,
                detail="Rate limit threshold reached.",
            )
            return RequestDecision(
                allowed=False,
                status_code=429,
                detail="Rate limit exceeded. Retry after 60 seconds.",
                identity=identity,
            )
        entries.append(now)
        return RequestDecision(allowed=True, identity=identity)

    def record_response(self, status_code: int) -> None:
        self._request_count += 1
        key = str(status_code)
        self._status_counts[key] = self._status_counts.get(key, 0) + 1
        if status_code >= 500:
            self._server_error_count += 1
            self._record_audit_event(
                event_type="SERVER_ERROR_RESPONSE",
                severity="ERROR",
                method=None,
                path=None,
                identity="system",
                detail=f"Server responded with status {status_code}.",
            )
            self._trigger_threshold_alert(
                metric_name="server_errors_total",
                count=self._server_error_count,
                threshold=self.server_error_alert_threshold,
                detail="Server error threshold reached.",
            )

    def record_upload_rejection(self, *, reason: str, quarantined: bool) -> None:
        self._upload_rejected_count += 1
        if quarantined:
            self._upload_quarantined_count += 1
        self._upload_rejections_by_reason[reason] = self._upload_rejections_by_reason.get(reason, 0) + 1
        self._record_audit_event(
            event_type="UPLOAD_REJECTED",
            severity="WARN",
            method=None,
            path=None,
            identity="system",
            detail=f"reason={reason} quarantined={quarantined}",
        )

    def _record_audit_event(
        self,
        *,
        event_type: str,
        severity: str,
        method: str | None,
        path: str | None,
        identity: str,
        detail: str,
    ) -> None:
        self._audit_events.append(
            {
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "event_type": event_type,
                "severity": severity,
                "method": method,
                "path": path,
                "identity": identity,
                "detail": detail,
            }
        )

    def _trigger_threshold_alert(self, *, metric_name: str, count: int, threshold: int, detail: str) -> None:
        if threshold <= 0 or count < threshold:
            return
        self._active_alerts.add(metric_name)
        self._last_alert = detail
        self._record_audit_event(
            event_type="ALERT_THRESHOLD_REACHED",
            severity="ERROR",
            method=None,
            path=None,
            identity="system",
            detail=f"{detail} metric={metric_name} count={count} threshold={threshold}",
        )

    def metrics_snapshot(self) -> dict[str, object]:
        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "security_enabled": self.enabled,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "requests_total": self._request_count,
            "status_counts": dict(self._status_counts),
            "auth_failures_total": self._auth_fail_count,
            "forbidden_total": self._forbidden_count,
            "rate_limited_total": self._rate_limited_count,
            "server_errors_total": self._server_error_count,
            "upload_rejected_total": self._upload_rejected_count,
            "upload_quarantined_total": self._upload_quarantined_count,
            "upload_rejections_by_reason": dict(self._upload_rejections_by_reason),
            "alert_policy": {
                "auth_failure_alert_threshold": self.auth_failure_alert_threshold,
                "rate_limit_alert_threshold": self.rate_limit_alert_threshold,
                "server_error_alert_threshold": self.server_error_alert_threshold,
            },
            "active_alerts": sorted(self._active_alerts),
            "last_alert": self._last_alert,
            "recent_audit_events": list(self._audit_events),
        }
