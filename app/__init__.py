"""Ensure SSL is configured before any service module makes HTTPS requests."""
from app.bootstrap import configure_ssl

configure_ssl()
