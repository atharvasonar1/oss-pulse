"""Cleanup utility for deduplicating risk_scores rows by project."""

from __future__ import annotations

from sqlalchemy import delete, func, select

from backend.db.models import RiskScore
from backend.db.session import get_session


def main() -> None:
    with get_session() as session:
        before_total = session.execute(select(func.count(RiskScore.id))).scalar_one()

        project_ids = session.execute(select(RiskScore.project_id).distinct()).scalars().all()
        deleted_total = 0
        touched_projects = 0

        for project_id in project_ids:
            ordered_ids = session.execute(
                select(RiskScore.id)
                .where(RiskScore.project_id == project_id)
                .order_by(RiskScore.scored_at.desc(), RiskScore.id.desc())
            ).scalars().all()

            if len(ordered_ids) <= 1:
                continue

            keep_id = ordered_ids[0]
            delete_result = session.execute(
                delete(RiskScore).where(
                    RiskScore.project_id == project_id,
                    RiskScore.id != keep_id,
                )
            )
            deleted_count = int(delete_result.rowcount or 0)
            deleted_total += deleted_count
            touched_projects += 1

        after_total = session.execute(select(func.count(RiskScore.id))).scalar_one()

        print(f"RiskScore rows before: {before_total}")
        print(f"RiskScore rows after: {after_total}")
        print(f"RiskScore rows deleted: {deleted_total}")
        print(f"Projects deduplicated: {touched_projects}")


if __name__ == "__main__":
    main()
