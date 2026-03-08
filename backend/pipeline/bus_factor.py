"""Bus factor computation utilities."""

from __future__ import annotations


def calculate_bus_factor(contributors: list[dict]) -> int:
    """Return the number of contributors needed to reach 50% of commits."""
    if not contributors:
        return 0

    totals = [int(item.get("total", 0)) for item in contributors]
    positive_totals = [total for total in totals if total > 0]
    if not positive_totals:
        return 0
    if len(positive_totals) == 1:
        return 1

    positive_totals.sort(reverse=True)
    total_commits = sum(positive_totals)
    cumulative = 0

    for index, commits in enumerate(positive_totals, start=1):
        cumulative += commits
        if cumulative / total_commits >= 0.5:
            return index

    return len(positive_totals)
