"""
Application bootstrap helpers.

On Windows (and some corporate networks), Python may not trust the system
certificate store, causing HTTPS failures for scraping, Gemini, and pip.
"""

import logging
import os

logger = logging.getLogger(__name__)

_ssl_configured = False


def configure_ssl() -> None:
    """Configure HTTPS certificate verification (safe to call multiple times)."""
    global _ssl_configured
    if _ssl_configured:
        return

    # Preferred on Windows: use the OS certificate store.
    try:
        import truststore

        truststore.inject_into_ssl()
        logger.debug("SSL: using truststore (OS certificate store)")
        _ssl_configured = True
        return
    except ImportError:
        logger.debug("SSL: truststore not installed, trying certifi fallback")

    # Fallback: Mozilla CA bundle via certifi.
    try:
        import certifi

        ca_bundle = certifi.where()
        os.environ.setdefault("SSL_CERT_FILE", ca_bundle)
        os.environ.setdefault("REQUESTS_CA_BUNDLE", ca_bundle)
        logger.debug("SSL: using certifi CA bundle at %s", ca_bundle)
        _ssl_configured = True
    except ImportError:
        logger.warning(
            "SSL: neither truststore nor certifi is installed. "
            "HTTPS calls may fail. Run: pip install truststore certifi"
        )
