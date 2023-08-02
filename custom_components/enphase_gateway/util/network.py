"""Network utils"""

from ipaddress import IPv6Address


def is_ipv6_address(address: str) -> bool:
    """Check if a given string is an IPv6 address."""
    try:
        IPv6Address(address)
    except ValueError:
        return False

    return True