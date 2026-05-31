from typing import Literal

from app.db.postgres import get_pool
from app.repos.db_utils import sql_string_literal

IssueStatus = Literal["open", "in_progress", "blocked", "resolved", "closed"]
IssuePriority = Literal["low", "medium", "high", "critical"]
IssueUpdateType = Literal[
    "triage",
    "investigation",
    "customer_update",
    "internal_note",
    "technical_note",
    "resolution",
]


async def update_issue_status(
    issue_id: int,
    status: IssueStatus,
    user_id: int,
    note: str | None = None,
) -> dict:
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                """
                SELECT id, status
                FROM issues
                WHERE id = $1
                """,
                issue_id,
            )

            if existing is None:
                return {
                    "success": False,
                    "message": f"No issue found with id {issue_id}.",
                }

            updated = await conn.fetchrow(
                """
                UPDATE issues
                SET status = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                RETURNING id, customer_id, title, description, status, priority,
                          assigned_to, created_at, updated_at
                """,
                status,
                issue_id,
            )

            if note is not None:
                note = sql_string_literal(note)[1:-1]

            update_text = note or (
                f"Status changed from {existing['status']} to {status}."
            )

            await conn.execute(
                """
                INSERT INTO issue_updates (
                    issue_id,
                    updated_by,
                    update_type,
                    update_text
                )
                VALUES ($1, $2, $3, $4)
                """,
                issue_id,
                user_id,
                "resolution" if status in {"resolved", "closed"} else "internal_note",
                update_text,
            )

    return {
        "success": True,
        "message": f"Issue {issue_id} status updated to {status}.",
        "issue": dict(updated),
    }


async def add_issue_update(
    issue_id: int,
    update_text: str,
    update_type: IssueUpdateType,
    user_id: int,
) -> dict:
    update_text = sql_string_literal(update_text.strip())[1:-1]

    if not update_text:
        return {
            "success": False,
            "message": "Update text cannot be empty.",
        }

    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                """
                SELECT id
                FROM issues
                WHERE id = $1
                """,
                issue_id,
            )

            if issue is None:
                return {
                    "success": False,
                    "message": f"No issue found with id {issue_id}.",
                }

            inserted = await conn.fetchrow(
                """
                INSERT INTO issue_updates (
                    issue_id,
                    updated_by,
                    update_type,
                    update_text
                )
                VALUES ($1, $2, $3, $4)
                RETURNING id, issue_id, updated_by, update_type, update_text, created_at
                """,
                issue_id,
                user_id,
                update_type,
                update_text,
            )

    return {
        "success": True,
        "message": f"Update added to issue {issue_id}.",
        "issue_update": dict(inserted),
    }


async def create_issue(
    customer_id: int,
    title: str,
    description: str | None,
    priority: IssuePriority,
    user_id: int,
    assigned_to: int | None = None,
) -> dict:
    title = sql_string_literal(title.strip())[1:-1]
    if description:
        description = sql_string_literal(description.strip())[1:-1]

    if not title:
        return {
            "success": False,
            "message": "Issue title cannot be empty.",
        }

    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            customer = await conn.fetchrow(
                """
                SELECT id
                FROM customers
                WHERE id = $1
                """,
                customer_id,
            )

            if customer is None:
                return {
                    "success": False,
                    "message": f"No customer found with id {customer_id}.",
                }

            if assigned_to is not None:
                assignee = await conn.fetchrow(
                    """
                    SELECT id
                    FROM users
                    WHERE id = $1
                    """,
                    assigned_to,
                )

                if assignee is None:
                    return {
                        "success": False,
                        "message": f"No user found with id {assigned_to}.",
                    }

            inserted = await conn.fetchrow(
                """
                INSERT INTO issues (
                    customer_id,
                    title,
                    description,
                    status,
                    priority,
                    assigned_to
                )
                VALUES ($1, $2, $3, 'open', $4, $5)
                RETURNING id, customer_id, title, description, status, priority,
                          assigned_to, created_at, updated_at
                """,
                customer_id,
                title,
                description,
                priority,
                assigned_to,
            )

            await conn.execute(
                """
                INSERT INTO issue_updates (
                    issue_id,
                    updated_by,
                    update_type,
                    update_text
                )
                VALUES ($1, $2, 'triage', $3)
                """,
                inserted["id"],
                user_id,
                f"Issue created with priority {priority}.",
            )

    return {
        "success": True,
        "message": f"Issue {inserted['id']} created.",
        "issue": dict(inserted),
    }


async def assign_issue(
    issue_id: int,
    assigned_to: int,
    user_id: int,
) -> dict:
    pool = get_pool()

    async with pool.acquire() as conn:
        async with conn.transaction():
            issue = await conn.fetchrow(
                """
                SELECT id, assigned_to
                FROM issues
                WHERE id = $1
                """,
                issue_id,
            )

            if issue is None:
                return {
                    "success": False,
                    "message": f"No issue found with id {issue_id}.",
                }

            assignee = await conn.fetchrow(
                """
                SELECT id, full_name
                FROM users
                WHERE id = $1
                """,
                assigned_to,
            )

            if assignee is None:
                return {
                    "success": False,
                    "message": f"No user found with id {assigned_to}.",
                }

            updated = await conn.fetchrow(
                """
                UPDATE issues
                SET assigned_to = $1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $2
                RETURNING id, customer_id, title, description, status, priority,
                          assigned_to, created_at, updated_at
                """,
                assigned_to,
                issue_id,
            )

            await conn.execute(
                """
                INSERT INTO issue_updates (
                    issue_id,
                    updated_by,
                    update_type,
                    update_text
                )
                VALUES ($1, $2, 'internal_note', $3)
                """,
                issue_id,
                user_id,
                f"Issue assigned to {assignee['full_name']}.",
            )

    return {
        "success": True,
        "message": f"Issue {issue_id} assigned to {assignee['full_name']}.",
        "issue": dict(updated),
    }