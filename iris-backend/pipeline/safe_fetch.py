"""
Keeps a caller-supplied image URL from reaching anything but the public internet.

The image endpoint accepts a URL and fetches it from the server. Run on a laptop that only
reached the laptop itself; run on a hosted machine it can reach the host's own metadata
service and whatever else shares its private network. Every address behind a submitted URL is
checked before the request goes out, and again after each redirect, because a public host may
redirect to a private one.

The check resolves the name itself and the request resolves it again, so a name that changes
answers between the two could still slip through. Closing that needs the connection pinned to
the address that was checked, which is more machinery than a study of this size calls for.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import requests

MAX_REDIRECTS = 3


class UnsafeImageURL(Exception):
    """The URL points somewhere other than the public internet."""


def _unmapped(address):
    """An IPv4 address written as IPv6 is still that IPv4 address."""
    if address.version == 6:
        mapped = address.ipv4_mapped
        if mapped is not None:
            return mapped
    return address


def _is_public(address):
    address = _unmapped(address)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


def _addresses_for(host):
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as error:
        raise UnsafeImageURL(f"IRIS could not resolve {host}.") from error

    addresses = []
    for info in infos:
        try:
            addresses.append(ipaddress.ip_address(info[4][0]))
        except ValueError:
            continue
    return addresses


def check_public_url(url):
    """Returns the parsed URL, or raises UnsafeImageURL when it is not on the public internet."""
    parsed = urlparse(str(url or "").strip())

    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeImageURL("Image URL must be an http or https URL.")

    addresses = _addresses_for(parsed.hostname)
    if not addresses:
        raise UnsafeImageURL(f"IRIS could not resolve {parsed.hostname}.")

    for address in addresses:
        if not _is_public(address):
            raise UnsafeImageURL(
                "IRIS only fetches images from public internet addresses."
            )

    return parsed


def get_public_url(url, headers=None, timeout=10, stream=True):
    """
    Fetches a URL, checking every address it leads to, redirects included.

    requests follows redirects on its own, which would skip the check on every hop after the
    first, so the hops are followed here one at a time.
    """
    current = str(url or "").strip()

    for _ in range(MAX_REDIRECTS + 1):
        check_public_url(current)
        response = requests.get(
            current,
            headers=headers,
            stream=stream,
            timeout=timeout,
            allow_redirects=False,
        )

        if response.status_code not in {301, 302, 303, 307, 308}:
            return response

        location = response.headers.get("Location")
        response.close()

        if not location:
            raise UnsafeImageURL("The image URL redirected without saying where.")

        current = requests.compat.urljoin(current, location)

    raise UnsafeImageURL("The image URL redirected too many times.")
