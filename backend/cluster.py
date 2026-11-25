from collections import Counter
from datetime import datetime

from backend.models import Story
from backend.normalize import identifier, tokens


def similarity(a, b):
    left, right = tokens(a.title), tokens(b.title)
    shared = left & right
    # A lone company or politician is insufficient evidence of the same event.
    if len(shared) < 3:
        return 0.0
    return len(shared) / max(1, len(left | right))


def cluster(articles, sources, settings, previous=None, candidate_groups=None):
    previous = previous or {}
    groups = []
    used_ids = set()
    for article in sorted(articles, key=lambda a: (a.published_at, a.id)):
        best, score = None, settings["similarity_threshold"]
        for group in groups:
            anchor = group[0]
            hours = (
                abs(
                    (
                        datetime.fromisoformat(article.published_at)
                        - datetime.fromisoformat(anchor.published_at)
                    ).total_seconds()
                )
                / 3600
            )
            if article.language != anchor.language or hours > settings["cluster_hours"]:
                continue
            value = similarity(article, anchor)
            if value >= score:
                best, score = group, value
        if best is None:
            groups.append([article])
        else:
            best.append(article)
    # Horizon proposes semantic groups; preserve every article and enforce hard
    # language/time boundaries before joining existing lexical clusters.
    for candidate in candidate_groups or []:
        ids = set(candidate)
        selected = [group for group in groups if ids & {a.id for a in group}]
        if len(selected) < 2:
            continue
        joined = sorted(
            [a for group in selected for a in group], key=lambda a: (a.published_at, a.id)
        )
        span = (
            datetime.fromisoformat(joined[-1].published_at)
            - datetime.fromisoformat(joined[0].published_at)
        ).total_seconds() / 3600
        if len({a.language for a in joined}) != 1 or span > settings["cluster_hours"]:
            continue
        selected_ids = {id(group) for group in selected}
        groups = [group for group in groups if id(group) not in selected_ids] + [joined]
    source_map = {s.id: s for s in sources}
    stories = []
    for group in groups:
        anchor = group[0]
        historical = Counter(previous[a.id] for a in group if a.id in previous)
        story_id = next((sid for sid, _ in historical.most_common() if sid not in used_ids), None)
        story_id = story_id or "story-" + identifier(anchor.id)
        # A split can leave the anchor-derived ID assigned to another group
        # through its historical mapping. Fresh IDs must also be unused.
        suffix = 0
        while story_id in used_ids:
            suffix += 1
            story_id = "story-" + identifier(f"{anchor.id}:{suffix}")
        used_ids.add(story_id)
        counts, publishers = {}, {}
        for leaning in ("left", "centre", "right", "unknown"):
            selected = [a for a in group if source_map[a.source_id].political_leaning == leaning]
            counts[leaning] = len(selected)
            publishers[leaning] = len(
                {source_map[a.source_id].publisher_id or a.source_id for a in selected}
            )
        known = sum(1 for key, value in counts.items() if key != "unknown" and value)
        limits = [
            "Coverage reflects configured sources, not all reporting. Political labels are country-contextual editorial assessments."
        ]
        if known < 2:
            limits.append("Insufficient coverage for comparison.")
        if any(a.date_estimated for a in group):
            limits.append(
                "Some publication times were unavailable or invalid; collection time was used."
            )
        terms = Counter(term for a in group for term in tokens(a.title))
        common = sorted(t for t, n in terms.items() if n >= 2)[:12]
        stories.append(
            Story(
                id=story_id,
                title=anchor.title,
                overview=anchor.summary,
                first_published=anchor.published_at,
                updated_at=max(a.published_at for a in group),
                article_ids=[a.id for a in group],
                publisher_count=len(
                    {source_map[a.source_id].publisher_id or a.source_id for a in group}
                ),
                article_counts=counts,
                publisher_counts=publishers,
                category=anchor.category,
                countries=sorted({a.country for a in group}),
                language=anchor.language,
                common_terms=common,
                limitations=limits,
            )
        )
    return sorted(stories, key=lambda s: (s.updated_at, s.publisher_count), reverse=True)
