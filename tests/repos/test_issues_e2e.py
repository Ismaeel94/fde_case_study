import pytest

from app.db.postgres import get_pool
from app.repos.issues import (
    add_issue_update,
    assign_issue,
    create_issue,
    update_issue_status,
)

SUPPORT_USER_ID = 3
SALES_USER_ID = 2
CUSTOMER_ID = 1


async def _delete_issue(issue_id: int) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM issues WHERE id = $1", issue_id)


@pytest.mark.asyncio
async def test_create_issue_e2e(db_pool):
    result = await create_issue(
        customer_id=CUSTOMER_ID,
        title="E2E create issue",
        description="Created by e2e test",
        priority="medium",
        user_id=SUPPORT_USER_ID,
    )

    assert result["success"] is True
    assert result["issue"]["title"] == "E2E create issue"
    assert result["issue"]["status"] == "open"
    assert result["issue"]["customer_id"] == CUSTOMER_ID

    await _delete_issue(result["issue"]["id"])


@pytest.mark.asyncio
async def test_update_issue_status_e2e(db_pool):
    created = await create_issue(
        customer_id=CUSTOMER_ID,
        title="E2E status issue",
        description=None,
        priority="low",
        user_id=SUPPORT_USER_ID,
    )
    issue_id = created["issue"]["id"]

    try:
        result = await update_issue_status(
            issue_id=issue_id,
            status="in_progress",
            user_id=SUPPORT_USER_ID,
            note="E2E status update note",
        )

        assert result["success"] is True
        assert result["issue"]["status"] == "in_progress"
        assert "status updated" in result["message"].lower()
    finally:
        await _delete_issue(issue_id)


@pytest.mark.asyncio
async def test_add_issue_update_e2e(db_pool):
    created = await create_issue(
        customer_id=CUSTOMER_ID,
        title="E2E update issue",
        description=None,
        priority="low",
        user_id=SUPPORT_USER_ID,
    )
    issue_id = created["issue"]["id"]

    try:
        result = await add_issue_update(
            issue_id=issue_id,
            update_text="E2E issue update text",
            update_type="investigation",
            user_id=SUPPORT_USER_ID,
        )

        assert result["success"] is True
        assert result["issue_update"]["issue_id"] == issue_id
        assert result["issue_update"]["update_text"] == "E2E issue update text"
        assert result["issue_update"]["update_type"] == "investigation"
    finally:
        await _delete_issue(issue_id)


@pytest.mark.asyncio
async def test_assign_issue_e2e(db_pool):
    created = await create_issue(
        customer_id=CUSTOMER_ID,
        title="E2E assign issue",
        description=None,
        priority="high",
        user_id=SUPPORT_USER_ID,
    )
    issue_id = created["issue"]["id"]

    try:
        result = await assign_issue(
            issue_id=issue_id,
            assigned_to=SALES_USER_ID,
            user_id=SUPPORT_USER_ID,
        )

        assert result["success"] is True
        assert result["issue"]["assigned_to"] == SALES_USER_ID
        assert "assigned to Sales User" in result["message"]
    finally:
        await _delete_issue(issue_id)
