
"""
Beacon v0.15 — CDN Helper (CloudFront Signed URLs)
Chapter 15: The Cost of Scale

Generates CloudFront signed URLs for static/media assets.
Reduces origin load and improves global latency by serving
from edge locations.

Principle: "Build only your differentiators. Buy commodities."
  CloudFront is a commodity CDN. Don't build one.
"""

import base64
import hashlib
import os
from datetime import datetime, timedelta
from typing import Optional


class CloudFrontSigner:
    """
    Generates signed URLs for CloudFront private distributions.

    Uses RSA key-based signing with a configurable expiration window.
    Signed URLs prevent hotlinking and unauthorized access to paid content.

    Usage:
        signer = CloudFrontSigner(
            key_pair_id="APK...",
            private_key_path="/path/to/pk-APK....pem",
            domain="https://d123.cloudfront.net",
        )
        url = signer.sign("static/images/hero.jpg", expires_minutes=60)
    """

    def __init__(self, key_pair_id: str, private_key_path: str, domain: str):
        self.key_pair_id = key_pair_id
        self.domain = domain.rstrip("/")
        self._load_key(private_key_path)

    def _load_key(self, path: str):
        """Load the RSA private key from disk."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        with open(path, "rb") as f:
            self._private_key = serialization.load_pem_private_key(
                f.read(), password=None
            )

    def sign(self, path: str, expires_minutes: int = 60) -> str:
        """
        Generate a signed CloudFront URL.

        Args:
            path: S3 object key (e.g., 'static/images/hero.jpg').
            expires_minutes: URL validity window in minutes.

        Returns:
            A fully signed CloudFront URL.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding

        expires = int((datetime.utcnow() + timedelta(minutes=expires_minutes)).timestamp())

        # Build the policy: restrict access to this specific resource.
        resource = f"{self.domain}/{path.lstrip('/')}"
        policy = (
            f'{{"Statement":[{{'
            f'"Resource":"{resource}",'
            f'"Condition":{{"DateLessThan":{{"AWS:EpochTime":{expires}}}}}'
            f'}}]}}'
        ).encode("utf-8")

        # Sign with RSA-SHA1.
        signature = self._private_key.sign(policy, padding.PKCS1v15(), hashes.SHA1())
        encoded_sig = base64.b64encode(signature).decode("utf-8")
        # Make URL-safe.
        encoded_sig = encoded_sig.replace("+", "-").replace("=", "_").replace("/", "~")

        return (
            f"{resource}"
            f"?Policy={base64.b64encode(policy).decode('utf-8').replace('+','-').replace('=','_').replace('/','~')}"
            f"&Signature={encoded_sig}"
            f"&Key-Pair-Id={self.key_pair_id}"
        )

    def generate_media_url(self, key: str) -> str:
        """Convenience: generate a 24-hour signed URL for media assets."""
        return self.sign(key, expires_minutes=1440)


# Singleton: initialized from Django settings at startup.
_cdn_signer: Optional[CloudFrontSigner] = None


def get_cdn_signer() -> Optional[CloudFrontSigner]:
    """Lazy-init the CDN signer from Django settings."""
    global _cdn_signer
    if _cdn_signer is not None:
        return _cdn_signer

    from django.conf import settings

    key_pair_id = os.environ.get("CLOUDFRONT_KEY_PAIR_ID", "")
    private_key_path = os.environ.get("CLOUDFRONT_PRIVATE_KEY_PATH", "")
    domain = os.environ.get("CLOUDFRONT_DOMAIN", "")

    if key_pair_id and private_key_path and domain:
        try:
            _cdn_signer = CloudFrontSigner(key_pair_id, private_key_path, domain)
        except Exception:
            _cdn_signer = None

    return _cdn_signer


def get_cdn_url(path: str, expires_minutes: int = 60) -> str:
    """
    Generate a CDN URL (signed if configured, fallback to direct).

    Args:
        path: Object key / path.
        expires_minutes: URL validity.

    Returns:
        Full CDN URL for the asset.
    """
    signer = get_cdn_signer()
    if signer:
        return signer.sign(path, expires_minutes)

    # Fallback: unsigned URL.
    domain = os.environ.get("CLOUDFRONT_DOMAIN", "")
    return f"{domain}/{path.lstrip('/')}"
