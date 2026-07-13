
"""
Beacon v0.7 — Auth Interceptor for gRPC

Inter-service authentication via signed HMAC tokens. Each service
has a shared secret (SERVICE_SECRET). The caller signs the request
metadata with an HMAC; the callee verifies the signature.

Chapter 7, Principle 4: "Authentication is a cross-cutting concern. A
signed internal token is simpler than a shared session store."

Token format:
    Authorization: Bearer <service_name>:<timestamp>:<signature>
"""

import hashlib
import hmac
import logging
import os
import time

import grpc

logger = logging.getLogger("beacon.auth")

SERVICE_SECRET = os.environ.get(
    "BEACON_SERVICE_SECRET", "dev-secret-do-not-use-in-production"
)

# Tokens are valid for this many seconds.
TOKEN_TTL_SECONDS = 300


def create_auth_token(service_name: str) -> str:
    """Create a signed HMAC token for inter-service calls."""
    timestamp = str(int(time.time()))
    message = f"{service_name}:{timestamp}"
    signature = hmac.new(
        SERVICE_SECRET.encode(),
        message.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{service_name}:{timestamp}:{signature}"


def verify_auth_token(token: str) -> tuple[bool, str]:
    """Verify a signed HMAC token. Returns (is_valid, service_name)."""
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False, ""
        service_name, timestamp_str, signature = parts
        timestamp = int(timestamp_str)

        # Check token age.
        if abs(time.time() - timestamp) > TOKEN_TTL_SECONDS:
            logger.warning("Token expired: age=%ds", abs(time.time() - timestamp))
            return False, service_name

        # Verify signature.
        message = f"{service_name}:{timestamp_str}"
        expected = hmac.new(
            SERVICE_SECRET.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, signature):
            logger.warning("Token signature mismatch for %s", service_name)
            return False, service_name

        return True, service_name

    except (ValueError, IndexError) as exc:
        logger.warning("Invalid token format: %s", exc)
        return False, ""


class AuthInterceptor(grpc.ServerInterceptor):
    """
    gRPC server interceptor that validates HMAC tokens on every request.

    Rejects unauthenticated requests with UNAUTHENTICATED status.
    """

    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)

        auth_header = metadata.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = ""

        is_valid, service_name = verify_auth_token(token)
        if not is_valid:
            logger.warning("Auth failed for method=%s", handler_call_details.method)
            return _unauthenticated_handler(handler_call_details.method)

        logger.debug("Auth OK: service=%s method=%s", service_name, handler_call_details.method)
        return continuation(handler_call_details)


def _unauthenticated_handler(method):
    """Return a handler that always returns UNAUTHENTICATED."""
    def handler(request, context):
        context.abort(grpc.StatusCode.UNAUTHENTICATED, "Invalid or missing auth token")
    return grpc.unary_unary_rpc_method_handler(handler)
