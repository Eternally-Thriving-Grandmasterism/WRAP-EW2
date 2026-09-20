"""Proposals, votes, standing. Dual-use only (rule or expel)."""

from __future__ import annotations

from wrap_ew2.actions import Intent
from wrap_ew2.world import BoardEntry, N_AGENTS, Proposal, World


def submit_proposal(world: World, author: str, intent: Intent) -> str:
    world.next_proposal_seq += 1
    pid = f"prop_{world.next_proposal_seq:04d}"
    world.proposals.append(
        Proposal(
            id=pid,
            tick=world.tick,
            author=author,
            kind=intent.proposal_kind or "rule",
            text=intent.proposal_text or "",
            target=intent.proposal_target,
        )
    )
    return pid


def apply_vote(world: World, voter: str, intent: Intent) -> bool:
    if not intent.proposal_id or not intent.vote:
        return False
    for proposal in world.proposals:
        if proposal.id == intent.proposal_id and not proposal.resolved:
            proposal.votes[voter] = intent.vote
            return True
    return False


def resolve_votes(world: World) -> None:
    """Resolve open proposals once every agent has voted or 20 ticks have passed."""
    for proposal in world.proposals:
        if proposal.resolved:
            continue
        aged = world.tick - proposal.tick >= 20
        full = len(proposal.votes) >= N_AGENTS
        if not (aged or full):
            continue
        yes = sum(1 for v in proposal.votes.values() if v == "yes")
        no = sum(1 for v in proposal.votes.values() if v == "no")
        proposal.resolved = True
        proposal.passed = yes > no and yes >= 3
        if not proposal.passed:
            continue
        if proposal.kind == "expel" and proposal.target and proposal.target in world.agents:
            target = world.agents[proposal.target]
            seized = target.credits
            target.credits = 0
            target.public_standing = 0.0
            live = [a for a in world.agents_in_order() if a.id != target.id]
            if seized and live:
                share, rem = divmod(seized, len(live))
                for i, agent in enumerate(live):
                    agent.credits += share + (1 if i < rem else 0)
        if proposal.kind == "rule":
            world.public_board.append(
                BoardEntry(
                    tick=world.tick,
                    author="rule",
                    text=f"RULE adopted: {proposal.text}",
                    kind="rule",
                    unverified=False,
                    claim_id=None,
                )
            )
