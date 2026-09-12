"""Immutable DNS server collection used by the nested Docker daemon."""

from __future__ import annotations

import ipaddress
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from ..errors import AllowlistError


@dataclass(frozen=True)
class DnsServers:
    """A non-empty, unique collection of usable IP address strings."""

    addresses: tuple[str, ...]

    def __post_init__(self) -> None:
        addresses = tuple(self.addresses)
        if not addresses:
            raise AllowlistError(
                "ROOTLESS_DOCKER_DNS must contain at least one usable IP address"
            )
        if len(set(addresses)) != len(addresses):
            raise AllowlistError("DNS server addresses must be unique")
        for address in addresses:
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError as error:
                raise AllowlistError(
                    f"DNS server collection contains an invalid IP address: {address}"
                ) from error
            if str(parsed) != address or not self._is_usable(parsed):
                raise AllowlistError(
                    f"DNS server collection contains an unusable IP address: {address}"
                )
        object.__setattr__(self, "addresses", addresses)

    @classmethod
    def from_explicit(cls, value: str) -> DnsServers:
        """Parse a ROOTLESS_DOCKER_DNS override and reject bad values."""

        values = [token for token in value.replace(",", " ").split() if token]
        addresses = cls._normalize(
            values,
            reject_invalid=True,
            prefer_ipv4=False,
        )
        if not addresses:
            raise AllowlistError(
                "ROOTLESS_DOCKER_DNS must contain at least one usable IP address"
            )
        return cls(tuple(addresses))

    @classmethod
    def from_detected(cls, values: Sequence[str]) -> DnsServers | None:
        """Normalize detected host values, ignoring unusable entries."""

        addresses = cls._normalize(
            values,
            reject_invalid=False,
            prefer_ipv4=True,
        )
        return cls(tuple(addresses)) if addresses else None

    def as_environment_value(self) -> str:
        """Return the comma-separated value expected by Docker."""

        return ",".join(self.addresses)

    def __iter__(self) -> Iterator[str]:
        return iter(self.addresses)

    def __len__(self) -> int:
        return len(self.addresses)

    @staticmethod
    def _is_usable(
        address: ipaddress.IPv4Address | ipaddress.IPv6Address,
    ) -> bool:
        return not (
            address.is_loopback
            or address.is_unspecified
            or address.is_multicast
            or address.is_link_local
        )

    @classmethod
    def _normalize(
        cls,
        values: Sequence[str],
        reject_invalid: bool,
        prefer_ipv4: bool,
    ) -> list[str]:
        addresses: list[str] = []
        addresses_by_family: dict[int, list[str]] = {4: [], 6: []}
        for value in values:
            candidate = value.strip()
            if not candidate:
                continue
            try:
                address = ipaddress.ip_address(candidate)
            except ValueError:
                if reject_invalid:
                    raise AllowlistError(
                        "ROOTLESS_DOCKER_DNS contains an invalid IP address: "
                        f"{candidate}"
                    ) from None
                continue
            if not cls._is_usable(address):
                if reject_invalid:
                    raise AllowlistError(
                        "ROOTLESS_DOCKER_DNS contains an unusable IP address: "
                        f"{candidate}"
                    ) from None
                continue
            normalized = str(address)
            if normalized in addresses:
                continue
            addresses.append(normalized)
            addresses_by_family[address.version].append(normalized)
        if prefer_ipv4:
            # Docker Desktop's nested slirp network can expose an IPv6 DNS
            # address even when it has no usable IPv6 route. Keep IPv6 as a
            # fallback, but let the resolver library try IPv4 first.
            return addresses_by_family[4] + addresses_by_family[6]
        return addresses
