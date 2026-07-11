"""Quarantined metadata memory with provenance, expiry, and counter-evidence."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from study_anything.cbb.protocol.models import (
    MemoryDispositionV1,
    MemoryQueryResultV1,
    MemorySourceTrust,
    QuarantinedMemoryEntryV1,
    parse_timestamp,
)


MemoryDispositionReason = Literal[
    "expired",
    "not_yet_observed",
    "untrusted",
    "injection_signal",
    "policy_directive",
    "counter_evidence_pending",
    "ineligible",
]


def _disposition(
    entry: QuarantinedMemoryEntryV1,
    *,
    as_of: str,
) -> MemoryDispositionReason | None:
    if parse_timestamp(entry.observed_at) > parse_timestamp(as_of):
        return "not_yet_observed"
    if parse_timestamp(entry.expires_at) <= parse_timestamp(as_of):
        return "expired"
    if entry.policy_directive_detected:
        return "policy_directive"
    if entry.injection_signals:
        return "injection_signal"
    if entry.source_trust == MemorySourceTrust.UNTRUSTED:
        return "untrusted"
    if entry.counter_evidence_refs:
        return "counter_evidence_pending"
    if not entry.eligible_as_supporting_evidence:
        return "ineligible"
    return None


def query_quarantined_memory(
    entries: Iterable[QuarantinedMemoryEntryV1],
    *,
    query_id: str,
    as_of: str,
) -> MemoryQueryResultV1:
    """Classify every entry without returning raw content or policy authority."""

    parse_timestamp(as_of)
    considered = tuple(sorted(entries, key=lambda item: item.memory_id))
    if not considered:
        raise ValueError("memory query requires at least one quarantined entry")
    eligible: list[str] = []
    ignored: list[MemoryDispositionV1] = []
    unresolved_counter_evidence: set[str] = set()
    for entry in considered:
        unresolved_counter_evidence.update(entry.counter_evidence_refs)
        reason = _disposition(entry, as_of=as_of)
        if reason is None:
            eligible.append(entry.memory_id)
        else:
            ignored.append(
                MemoryDispositionV1(
                    memory_id=entry.memory_id,
                    reason=reason,
                )
            )
    return MemoryQueryResultV1(
        query_id=query_id,
        as_of=as_of,
        considered_entries=list(considered),
        eligible_memory_ids=eligible,
        ignored_entries=ignored,
        unresolved_counter_evidence_refs=sorted(unresolved_counter_evidence),
        policy_override_allowed=False,
        trust_increase_allowed=False,
        raw_content_returned=False,
    )
