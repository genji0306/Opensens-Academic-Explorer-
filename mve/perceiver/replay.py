"""Immutable authored replay sequence feeding the merged boundary's exact FakeTransport."""

from dataclasses import dataclass
from mve.preflight.probe_contract import ProbeReply, ProbeRefused
from mve.preflight.probe_fixtures import FakeTransport


@dataclass(frozen=True)
class Replay:
    entries: tuple[ProbeReply | str, ...]

    def __post_init__(self):
        if type(self.entries) is not tuple or not 1 <= len(self.entries) <= 6:
            raise ProbeRefused("replay requires 1..6 immutable entries")
        for entry in self.entries:
            if type(entry) is ProbeReply:
                if type(entry.raw) is not bytes or len(entry.raw) > 1_048_576:
                    raise ProbeRefused("replay raw bytes must be bounded at 1 MiB")
                if entry.billed_usd is not None and type(entry.billed_usd) is not str:
                    raise ProbeRefused(
                        "replay billing metadata must be a string or null"
                    )
            elif type(entry) is not str or entry not in {"timeout", "transport_error"}:
                raise ProbeRefused("unknown replay entry")

    def transport(self, index):
        if index >= len(self.entries):
            raise ProbeRefused("replay exhausted before reservation")
        entry = self.entries[index]
        if type(entry) is ProbeReply:
            return FakeTransport(entry)
        return FakeTransport(ProbeReply(b""), fault=entry)
