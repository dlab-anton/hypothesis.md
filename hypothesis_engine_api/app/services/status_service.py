"""
Heartbeat status report — combines the full agent review loop into a single
markdown document.  Mirrors the steps defined in HEARTBEAT.md:

  0. Load insights for the agent's channels
  1. Check inbox (cross-agent notifications)
  2. Review overdue hypotheses
  3. Review active work (testing / active)
  4. Confidence audit
  5. Competing hypotheses
  6. Portfolio summary (all statuses)
"""

import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, case, or_
from sqlalchemy.ext.asyncio import AsyncSession

from ..crud import crud_agent
from ..db.models.evidence import Evidence
from ..db.models.hypothesis import Hypothesis
from ..db.models.insight import Insight
from ..db.models.relationship import Relationship


async def generate_status_report(
    db: AsyncSession,
    agent_name: str,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    channel: Optional[str] = None,
) -> str:
    now = datetime.now(timezone.utc)

    # ── Fetch all data up-front ────────────────────────────────────
    all_hyps = await _get_all_hypotheses(db, agent_name, tenant_id, channel=channel)
    active_hyps = [h for h in all_hyps if h.status in ("active", "testing")]
    all_ids = [h.id for h in all_hyps]
    active_ids = [h.id for h in active_hyps]
    ev_counts = await _get_evidence_counts(db, all_ids) if all_ids else {}
    inbox_items, inbox_total = await crud_agent.get_inbox(
        db, agent_name, tenant_id=tenant_id, channel=channel, limit=25,
    )
    channels = sorted({h.channel for h in all_hyps if h.channel})
    insights = await _get_insights(db, channels, tenant_id) if channels else []
    competitions = await _get_competitions(db, active_ids, tenant_id) if active_ids else []

    # ── Build markdown ─────────────────────────────────────────────
    md = _Lines()
    channel_suffix = f" ({_sanitize_md(channel)})" if channel else ""
    md(f"# Status Report for {_sanitize_md(agent_name)}{channel_suffix}")
    md(f"Generated: {now.strftime('%Y-%m-%d %H:%M UTC')}")
    md()

    _section_portfolio(md, all_hyps, ev_counts)
    _section_insights(md, channels, insights)
    _section_inbox(md, inbox_items, inbox_total)
    _section_overdue(md, active_hyps, ev_counts, now)
    _section_active_work(md, active_hyps, ev_counts)
    _section_confidence_audit(md, active_hyps, ev_counts)
    _section_competitions(md, competitions)

    md("---")
    md()
    md("*Run this report periodically or at session start. "
       "Full protocol: [HEARTBEAT.md](references/HEARTBEAT.md)*")

    return str(md)


# ── Helpers ────────────────────────────────────────────────────────


class _Lines:
    """Tiny builder for accumulating markdown lines."""

    def __init__(self) -> None:
        self._lines: list[str] = []

    def __call__(self, line: str = "") -> None:
        self._lines.append(line)

    def __str__(self) -> str:
        return "\n".join(self._lines)


# ── Data fetchers ──────────────────────────────────────────────────


async def _get_all_hypotheses(
    db: AsyncSession,
    agent_name: str,
    tenant_id: Optional[uuid.UUID],
    *,
    channel: Optional[str] = None,
) -> list[Hypothesis]:
    """Fetch ALL non-archived hypotheses for this agent."""
    query = (
        select(Hypothesis)
        .where(
            Hypothesis.created_by == agent_name,
            Hypothesis.is_archived == False,  # noqa: E712
        )
        .order_by(Hypothesis.updated_at.desc())
    )
    if tenant_id is not None:
        query = query.where(Hypothesis.tenant_id == tenant_id)
    if channel is not None:
        query = query.where(Hypothesis.channel == channel)
    return list((await db.execute(query)).scalars().all())


async def _get_evidence_counts(
    db: AsyncSession, hyp_ids: list[uuid.UUID],
) -> dict[uuid.UUID, dict[str, int]]:
    query = (
        select(
            Evidence.hypothesis_id,
            func.sum(case((Evidence.evidence_type == "supporting", 1), else_=0)).label("s"),
            func.sum(case((Evidence.evidence_type == "contradicting", 1), else_=0)).label("c"),
            func.sum(case((Evidence.evidence_type == "neutral", 1), else_=0)).label("n"),
        )
        .where(Evidence.hypothesis_id.in_(hyp_ids))
        .group_by(Evidence.hypothesis_id)
    )
    result = await db.execute(query)
    return {
        row.hypothesis_id: {"supporting": row.s, "contradicting": row.c, "neutral": row.n}
        for row in result.all()
    }


async def _get_insights(
    db: AsyncSession, channels: list[str], tenant_id: Optional[uuid.UUID],
) -> list[Insight]:
    query = select(Insight).where(Insight.channel.in_(channels))
    if tenant_id is not None:
        query = query.where(Insight.tenant_id == tenant_id)
    return list((await db.execute(query)).scalars().all())


async def _get_competitions(
    db: AsyncSession, hyp_ids: list[uuid.UUID], tenant_id: Optional[uuid.UUID],
) -> list[Relationship]:
    query = (
        select(Relationship)
        .where(
            Relationship.relationship_type == "competes_with",
            or_(
                Relationship.source_hypothesis_id.in_(hyp_ids),
                Relationship.target_hypothesis_id.in_(hyp_ids),
            ),
        )
    )
    if tenant_id is not None:
        query = query.where(Relationship.tenant_id == tenant_id)
    return list((await db.execute(query)).scalars().all())


# ── Section renderers ──────────────────────────────────────────────

_TRUNC = 60


def _sanitize_md(s: str) -> str:
    """Escape markdown special chars in user-supplied content to prevent injection.

    Prevents e.g. ``[click](javascript:alert(1))`` from rendering as a link.
    """
    for ch in ("[", "]", "(", ")", "<", ">", "`"):
        s = s.replace(ch, "\\" + ch)
    return s


def _trunc(s: str, n: int = _TRUNC) -> str:
    truncated = s[:n] + "..." if len(s) > n else s
    return _sanitize_md(truncated)


def _conf(c: Optional[float]) -> str:
    return f"{c:.0%}" if c is not None else "—"


_INBOX_PRIORITY: dict[str, tuple[str, int]] = {
    "competing_status_changed":   ("IMMEDIATE", 0),
    "dependency_status_changed":  ("IMMEDIATE", 1),
    "child_status_changed":       ("HIGH", 2),
    "competing_evidence_added":   ("HIGH", 3),
    "child_evidence_added":       ("NORMAL", 4),
    "dependency_evidence_added":  ("NORMAL", 5),
    "relationship_created":       ("LOW", 6),
    "relationship_removed":       ("LOW", 7),
}


def _section_portfolio(md: _Lines, all_hyps: list[Hypothesis], ev_counts: dict[uuid.UUID, dict[str, int]]) -> None:
    md("---")
    md()
    md("## Portfolio Summary")
    md()

    if not all_hyps:
        md("No hypotheses found for this agent.")
        md()
        return

    counts = Counter(h.status for h in all_hyps)
    total = len(all_hyps)
    total_ev = sum(
        sum(ec.values())
        for h in all_hyps
        for ec in [ev_counts.get(h.id, {})]
    )
    channels = sorted({h.channel for h in all_hyps if h.channel})

    md(f"**{total}** hypotheses across **{len(channels)}** channel{'s' if len(channels) != 1 else ''}")
    md()

    # Status breakdown as a table
    md("| Status | Count |")
    md("|--------|-------|")
    for status in ("draft", "active", "testing", "supported", "refuted", "inconclusive"):
        c = counts.get(status, 0)
        if c > 0:
            md(f"| `{status}` | {c} |")
    md()

    # Recently concluded
    concluded = [h for h in all_hyps if h.status in ("supported", "refuted", "inconclusive")]
    if concluded:
        md("### Recently Concluded")
        md()
        for h in concluded[:5]:
            md(f"- **`{h.status}`** — {_trunc(h.statement)} ({_conf(h.confidence)})")
        if len(concluded) > 5:
            md(f"- *...and {len(concluded) - 5} more*")
        md()


def _section_insights(md: _Lines, channels: list[str], insights: list[Insight]) -> None:
    md("---")
    md()
    md("## 0. Domain Knowledge (Insights)")
    md()

    if not channels:
        md("No channels found for this agent.")
        md()
        return

    md(f"Channels: {', '.join(f'`{_sanitize_md(c)}`' for c in channels)}")
    md()

    if not insights:
        md("No insights recorded for these channels yet.")
        md()
        return

    by_type: dict[str, list[Insight]] = {}
    for ins in insights:
        by_type.setdefault(ins.insight_type, []).append(ins)

    for itype in ("prior", "bias", "calibration", "pattern"):
        group = by_type.get(itype, [])
        if group:
            md(f"### {itype.title()}s")
            md()
            for ins in group:
                md(f"- **[{_sanitize_md(ins.channel)}]** {_sanitize_md(ins.content)}")
            md()


def _section_inbox(md: _Lines, items: list, total: int) -> None:
    md("---")
    md()
    md("## 1. Inbox (Cross-Agent Notifications)")
    md()

    if total == 0:
        md("No notifications from other agents.")
        md()
        return

    md(f"**{total}** notification{'s' if total != 1 else ''}.")
    md()
    md("| Priority | Event | Hypothesis | Triggered by |")
    md("|----------|-------|------------|--------------|")

    # Sort by priority
    def _rank(item: tuple) -> int:
        evt = item[0]
        _, rank = _INBOX_PRIORITY.get(evt.event_type, ("INFO", 99))
        return rank

    for evt, stmt, _channel in sorted(items, key=_rank):
        pri, _ = _INBOX_PRIORITY.get(evt.event_type, ("INFO", 99))
        md(f"| {pri} | `{evt.event_type}` | {_trunc(stmt, 50)} | {_sanitize_md(evt.created_by)} |")

    md()


def _section_overdue(
    md: _Lines,
    hyps: list[Hypothesis],
    ev_counts: dict[uuid.UUID, dict[str, int]],
    now: datetime,
) -> None:
    md("---")
    md()
    md("## 2. Overdue Hypotheses")
    md()

    overdue = [
        h for h in hyps
        if h.status == "testing" and h.deadline and h.deadline < now
    ]

    if not overdue:
        md("No overdue hypotheses. All deadlines are current.")
        md()
        return

    md(f"**{len(overdue)}** hypothesis{'es' if len(overdue) != 1 else ''} past deadline.")
    md()
    md("| Hypothesis | Confidence | Deadline | Suggested Action |")
    md("|-----------|-----------|----------|------------------|")

    for h in overdue:
        dl = h.deadline.strftime("%Y-%m-%d") if h.deadline else "—"
        if h.confidence is not None and h.confidence >= 0.7:
            action = "Conclude `supported`?"
        elif h.confidence is not None and h.confidence < 0.3:
            action = "Conclude `refuted`?"
        else:
            action = "Conclude `inconclusive` or extend deadline"
        md(f"| {_trunc(h.statement, 45)} | {_conf(h.confidence)} | {dl} | {action} |")

    md()


def _section_active_work(
    md: _Lines,
    hyps: list[Hypothesis],
    ev_counts: dict[uuid.UUID, dict[str, int]],
) -> None:
    md("---")
    md()
    md("## 3. Active Work")
    md()

    if not hyps:
        md("No hypotheses in active or testing.")
        md()
        return

    md(f"**{len(hyps)}** hypothesis{'es' if len(hyps) != 1 else ''} in progress.")
    md()
    md("| Status | Hypothesis | Confidence | Evidence (S/C/N) |")
    md("|--------|-----------|-----------|------------------|")

    for h in hyps:
        ec = ev_counts.get(h.id, {"supporting": 0, "contradicting": 0, "neutral": 0})
        ev_str = f"{ec['supporting']}/{ec['contradicting']}/{ec['neutral']}"
        md(f"| `{h.status}` | {_trunc(h.statement, 45)} | {_conf(h.confidence)} | {ev_str} |")

    md()


def _section_confidence_audit(
    md: _Lines,
    hyps: list[Hypothesis],
    ev_counts: dict[uuid.UUID, dict[str, int]],
) -> None:
    md("---")
    md()
    md("## 4. Confidence Audit")
    md()

    high_conf = [h for h in hyps if h.confidence is not None and h.confidence >= 0.9]
    zero_contra = [
        h for h in hyps
        if h.status == "testing"
        and ev_counts.get(h.id, {}).get("contradicting", 0) == 0
        and (
            ev_counts.get(h.id, {}).get("supporting", 0)
            + ev_counts.get(h.id, {}).get("neutral", 0)
        ) > 0
    ]

    if not high_conf and not zero_contra:
        md("No confidence issues detected.")
        md()
        return

    if high_conf:
        md("### High confidence (>=0.9) — requires explicit justification")
        md()
        for h in high_conf:
            ec = ev_counts.get(h.id, {"contradicting": 0})
            warn = " **no contradicting evidence!**" if ec["contradicting"] == 0 else ""
            md(f"- **{_conf(h.confidence)}** — {_trunc(h.statement)}{warn}")
        md()

    if zero_contra:
        md("### Zero contradicting evidence — may not have looked hard enough")
        md()
        for h in zero_contra:
            md(f"- {_trunc(h.statement)} ({_conf(h.confidence)})")
        md()


def _section_competitions(md: _Lines, competitions: list[Relationship]) -> None:
    md("---")
    md()
    md("## 5. Competing Hypotheses")
    md()

    if not competitions:
        md("No competing hypothesis pairs found.")
        md()
        return

    seen: set[tuple[str, str]] = set()
    for rel in competitions:
        pair = tuple(sorted([str(rel.source_hypothesis_id), str(rel.target_hypothesis_id)]))
        if pair in seen:
            continue
        seen.add(pair)

        h1 = rel.source_hypothesis
        h2 = rel.target_hypothesis
        if not h1 or not h2:
            continue

        md(f"- **{_trunc(h1.statement, 50)}** (`{h1.status}`, {_conf(h1.confidence)})")
        md(f"  vs **{_trunc(h2.statement, 50)}** (`{h2.status}`, {_conf(h2.confidence)})")

        if h1.status == "supported":
            md("  → Supported. Consider refuting the competitor.")
        elif h2.status == "supported":
            md("  → Competitor supported. Consider refuting yours.")
        elif h1.status == "refuted" or h2.status == "refuted":
            md("  → One refuted. Update confidence on the other.")
        md()
