"""EPG sources. Each source exposes `.name`, `.channels` and `.load()`."""

from __future__ import annotations

from typing import Protocol

from ..models import Channel, Programme
from .bbc import BbcSource
from .xmltv import XmltvSource, parse_xmltv_time


class Source(Protocol):
    name: str
    channels: dict[str, Channel]

    def load(self) -> "object": ...  # Iterator[Programme]


def build_source(spec: dict) -> Source:
    """Instantiate a source from its config table."""
    spec = dict(spec)
    kind = spec.pop("type", "xmltv")
    name = spec.pop("name", kind)
    if kind == "xmltv":
        return XmltvSource(name, **spec)
    if kind == "bbc":
        return BbcSource(name, **spec)
    raise ValueError(f"unknown source type {kind!r} (expected 'xmltv' or 'bbc')")


__all__ = [
    "BbcSource",
    "Channel",
    "Programme",
    "Source",
    "XmltvSource",
    "build_source",
    "parse_xmltv_time",
]
