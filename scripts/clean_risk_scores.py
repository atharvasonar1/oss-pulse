"""Cleanup utility for deduplicating risk_scores rows by project and ISO week."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from backend.db.models import RiskScore
from backend.db.session import get_session


def main() -> None:
    with get_session() as session:
        before_total = session.execute(select(func.count(RiskScore.id))).scalar_one()

        rows = session.execute(
            select(RiskScore.id, RiskScore.project_id, RiskScore.scored_at).order_by(
                RiskScore.project_id.asc(),
                RiskScore.scored_at.desc(),
                RiskScore.id.desc(),
            )
        ).all()

        keep_ids: set[int] = set()
        seen_groups: set[tuple[int, int, int]] = set()

        for score_id, project_id, scored_at in rows:
            iso = scored_at.isocalendar()
            group_key = (project_id, iso.year, iso.week)
            if group_key in seen_groups:
                continue

            seen_groups.add(group_key)
            keep_ids.add(score_id)

        deleted_total = 0
        if rows:
            delete_result = session.execute(
                delete(RiskScore).where(RiskScore.id.not_in(keep_ids))
            )
            deleted_total = int(delete_result.rowcount or 0)

        after_total = session.execute(select(func.count(RiskScore.id))).scalar_one()

        print(f"RiskScore rows before: {before_total}")
        print(f"RiskScore rows after: {after_total}")
        print(f"RiskScore rows deleted: {deleted_total}")


if __name__ == "__main__":
    main()
