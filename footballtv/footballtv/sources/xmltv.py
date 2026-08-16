"""XMLTV source: reads any XMLTV guide from a URL or a local file.

XMLTV is the lingua franca of TV guides — it is what epgshare01, epg.pw,
the iptv-org grabber, WebGrab+Plus, Tvheadend and Jellyfin all speak — so a
single parser here covers every broadcaster the user cares about.
"""

from __future__ import annotations

import io
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

from ..http import fetch
from ..models import Channel, Programme

log = logging.getLogger(__name__)

# "20260816200000 +0100", "20260816200000", "202608162000 +0100"
_XMLTV_TIME = re.compile(r"^\s*(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})?\s*([+-]\d{2}:?\d{2})?")


def parse_xmltv_time(value: str) -> datetime | None:
    """Parse an XMLTV timestamp. Naive timestamps are assumed to be UTC."""
    if not value:
        return None
    match = _XMLTV_TIME.match(value)
    if not match:
        return None
    year, month, day, hour, minute, second, offset = match.groups()
    try:
        base = datetime(
            int(year), int(month), int(day), int(hour), int(minute), int(second or 0)
        )
    except ValueError:
        return None
    if offset:
        offset = offset.replace(":", "")
        sign = 1 if offset[0] == "+" else -1
        delta = timedelta(hours=int(offset[1:3]), minutes=int(offset[3:5]))
        return base.replace(tzinfo=timezone(sign * delta))
    return base.replace(tzinfo=timezone.utc)


class XmltvSource:
    """Streams an XMLTV document into `Programme` objects."""

    type = "xmltv"

    def __init__(
        self,
        name: str,
        *,
        url: str = "",
        path: str = "",
        max_age: int = 6 * 3600,
        channel_filter: list[str] | None = None,
    ) -> None:
        if not url and not path:
            raise ValueError(f"source {name!r}: either 'url' or 'path' is required")
        self.name = name
        self.url = url
        self.path = path
        self.max_age = max_age
        self.channel_filter = [c.lower() for c in (channel_filter or [])]
        self.channels: dict[str, Channel] = {}

    def _open(self) -> io.BufferedIOBase:
        if self.path:
            data = Path(self.path).expanduser().read_bytes()
            if data[:2] == b"\x1f\x8b":
                import gzip

                data = gzip.decompress(data)
        else:
            data = fetch(self.url, max_age=self.max_age)
        return io.BytesIO(data)

    def load(self) -> Iterator[Programme]:
        """Yield every programme in the guide.

        `iterparse` keeps memory flat: elements are cleared as soon as they are
        converted, which matters for the 100 MB+ national feeds.
        """
        stream = self._open()
        channel_names: dict[str, list[str]] = {}
        skipped = 0

        for event, element in ET.iterparse(stream, events=("end",)):
            if element.tag == "channel":
                channel_id = element.get("id") or ""
                names = [
                    (node.text or "").strip()
                    for node in element.findall("display-name")
                    if (node.text or "").strip()
                ]
                if channel_id:
                    channel_names[channel_id] = names
                    self.channels[channel_id] = Channel(channel_id, names, self.name)
                element.clear()
                continue

            if element.tag != "programme":
                continue

            channel_id = element.get("channel") or ""
            start = parse_xmltv_time(element.get("start") or "")
            if not channel_id or start is None:
                skipped += 1
                element.clear()
                continue

            if self.channel_filter and not self._channel_wanted(channel_id, channel_names):
                element.clear()
                continue

            names = channel_names.get(channel_id, [])
            yield Programme(
                channel_id=channel_id,
                channel_name=names[0] if names else channel_id,
                start=start,
                stop=parse_xmltv_time(element.get("stop") or ""),
                title=_text(element, "title"),
                subtitle=_text(element, "sub-title"),
                description=_text(element, "desc"),
                categories=[
                    (node.text or "").strip()
                    for node in element.findall("category")
                    if (node.text or "").strip()
                ],
                is_repeat=element.find("previously-shown") is not None,
                source=self.name,
                url=_text(element, "url"),
            )
            element.clear()

        if skipped:
            log.debug("%s: skipped %d unparsable programme entries", self.name, skipped)

    def _channel_wanted(self, channel_id: str, channel_names: dict[str, list[str]]) -> bool:
        haystack = [channel_id.lower(), *(n.lower() for n in channel_names.get(channel_id, []))]
        return any(needle in value for needle in self.channel_filter for value in haystack)


def _text(element: ET.Element, tag: str) -> str:
    """First non-empty value of `tag`, preferring English where languages differ."""
    nodes = [node for node in element.findall(tag) if (node.text or "").strip()]
    if not nodes:
        return ""
    for node in nodes:
        if (node.get("lang") or "").lower().startswith("en"):
            return (node.text or "").strip()
    return (nodes[0].text or "").strip()
