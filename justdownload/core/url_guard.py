from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit, urlunsplit


class URLRejected(ValueError):
    """Raised when a URL violates the application's network policy."""


def _is_public_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value.split("%", 1)[0])
    except ValueError:
        return False
    return bool(address.is_global and not (
        address.is_private or address.is_loopback or address.is_link_local
        or address.is_multicast or address.is_reserved or address.is_unspecified
    ))


def validate_url(url: str) -> str:
    """Normalize and validate a direct HTTP(S) media URL.

    All resolved addresses must be globally routable. Redirects are validated
    separately before they are followed. The app never accepts credentials in
    URLs, localhost, private-network destinations, or non-web schemes.
    """
    if not isinstance(url, str) or len(url) > 4096:
        raise URLRejected("Enter a valid media URL (maximum 4,096 characters).")
    value = url.strip()
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise URLRejected("The URL format is invalid.") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise URLRejected("Only direct HTTP or HTTPS media URLs are supported.")
    if not parts.hostname:
        raise URLRejected("The URL must include a hostname.")
    if parts.username is not None or parts.password is not None:
        raise URLRejected("URLs containing usernames or passwords are not accepted.")
    if port not in (None, 80, 443):
        raise URLRejected("For safety, only standard HTTP and HTTPS ports are supported.")
    host = parts.hostname.rstrip(".").encode("idna").decode("ascii").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".localhost") or host.endswith(".local"):
        raise URLRejected("Local and private network destinations are not supported.")
    try:
        literal = ipaddress.ip_address(host)
        if not _is_public_ip(str(literal)):
            raise URLRejected("Local and private network destinations are not supported.")
    except ValueError:
        try:
            records = socket.getaddrinfo(host, port or (443 if parts.scheme.lower() == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise URLRejected("The hostname could not be resolved.") from exc
        addresses = {record[4][0] for record in records}
        if not addresses or any(not _is_public_ip(address) for address in addresses):
            raise URLRejected("The hostname resolves to a local or non-public address.")
    return urlunsplit((parts.scheme.lower(), parts.netloc, parts.path or "/", parts.query, ""))
