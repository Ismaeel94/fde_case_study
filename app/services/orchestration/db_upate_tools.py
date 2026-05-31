from langchain_core.tools import tool
from app.repos.issues import (
    update_issue_status,
    add_issue_update,
    create_issue,
    assign_issue,
)


def build_write_tools(user_id: int):
    @tool
    async def update_issue_status_tool(issue_id: int, status: str, note: str | None = None) -> dict:
        """Update the status of an existing customer issue."""
        return await update_issue_status(
            issue_id=issue_id,
            status=status,
            user_id=user_id,
            note=note,
        )

    @tool
    async def add_issue_update_tool(issue_id: int, update_text: str, update_type: str) -> dict:
        """Add a note/update to an existing customer issue."""
        return await add_issue_update(
            issue_id=issue_id,
            update_text=update_text,
            update_type=update_type,
            user_id=user_id,
        )

    @tool
    async def create_issue_tool(
        customer_id: int,
        title: str,
        description: str | None,
        priority: str,
        assigned_to: int | None = None,
    ) -> dict:
        """Create a new customer issue."""
        return await create_issue(
            customer_id=customer_id,
            title=title,
            description=description,
            priority=priority,
            assigned_to=assigned_to,
            user_id=user_id,
        )

    @tool
    async def assign_issue_tool(issue_id: int, assigned_to: int) -> dict:
        """Assign an existing issue to a user."""
        return await assign_issue(
            issue_id=issue_id,
            assigned_to=assigned_to,
            user_id=user_id,
        )

    return [
        update_issue_status_tool,
        add_issue_update_tool,
        create_issue_tool,
        assign_issue_tool,
    ]