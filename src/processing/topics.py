"""Non-destructive form of Horizon's semantic topic deduplication.

Extracted from HorizonOrchestrator.merge_topic_duplicates so consumers such as
NewsLens can keep all source records while sharing the same grouping behavior.
"""

from collections import defaultdict

from ..ai.prompting.common import UNTRUSTED_INPUT_RULE
from ..ai.prompting.deduplication import TOPIC_DEDUP_SYSTEM, TOPIC_DEDUP_USER
from ..ai.utils import parse_json_response


async def find_topic_groups(items, client):
    """Return disjoint valid index groups; never mutate or remove input items."""
    if len(items) < 2:
        return []
    lines = []
    for index, item in enumerate(items):
        analysis = item.processing.analysis if item.processing else None
        tags = ", ".join(analysis.tags) if analysis and analysis.tags else "—"
        summary = analysis.summary if analysis else "—"
        lines.append(f"[{index}] {item.title}\n    Tags: {tags}\n    Summary: {summary}")
    response = await client.complete(
        system=TOPIC_DEDUP_SYSTEM + "\n\n" + UNTRUSTED_INPUT_RULE,
        user=TOPIC_DEDUP_USER.format(items="\n\n".join(lines)),
    )
    result = parse_json_response(response)
    if not isinstance(result, dict):
        raise ValueError("Invalid topic grouping response")
    groups = result.get("duplicates", [])
    if not isinstance(groups, list):
        raise ValueError("Invalid topic grouping list")
    parent = list(range(len(items)))

    def find(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    grouped = set()
    for group in groups:
        if not isinstance(group, list):
            continue
        members = sorted(
            {
                index
                for index in group
                if isinstance(index, int)
                and not isinstance(index, bool)
                and 0 <= index < len(items)
            }
        )
        if len(members) < 2:
            continue
        grouped.update(members)
        for index in members[1:]:
            parent[find(index)] = find(members[0])
    clusters = defaultdict(list)
    for index in sorted(grouped):
        clusters[find(index)].append(index)
    return list(clusters.values())
