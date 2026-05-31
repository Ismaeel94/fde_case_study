import asyncio

from app.repos.db_utils import sql_string_literal
from app.services.mcp_client import get_column, get_first_row, query_postgres


class CustomerRepository:
    async def get_customer_by_name(self, customer_name: str) -> dict | None:
        safe_name = sql_string_literal(customer_name)

        sql = f"""
        SELECT id, name
        FROM customers
        WHERE LOWER(name) = LOWER({safe_name})
        LIMIT 1;
        """

        rows = await self.query_postgres(sql)
        customer = get_first_row(rows)
        print("customer first row", customer)

        customer_id = get_column(customer, "id")
        print("customer id", customer_id)

        if customer_id is None:
            return None

        return customer

    async def get_open_issues(self, customer_id: int) -> list[dict]:
        if not isinstance(customer_id, int):
            raise ValueError("customer_id must be an integer")

        sql = f"""
        SELECT id, customer_id, title, status, priority, created_at
        FROM issues
        WHERE customer_id = {customer_id}
          AND status IN ('open', 'in_progress')
        ORDER BY created_at DESC;
        """

        return await self.query_postgres(sql)

    async def get_recent_issue_activity(self, customer_id: int, limit: int = 20) -> list[dict]:
        if not isinstance(customer_id, int):
            raise ValueError("customer_id must be an integer")

        limit = max(1, min(limit, 50))

        sql = f"""
        SELECT 
            ia.id,
            ia.issue_id,
            i.title AS issue_title,
            ia.update_type,
            ia.update_text,
            ia.updated_by,
            ia.created_at
        FROM issue_updates ia
        JOIN issues i ON ia.issue_id = i.id
        WHERE i.customer_id = {customer_id}
        ORDER BY ia.created_at DESC
        LIMIT {limit};
        """

        return await self.query_postgres(sql)

    async def get_customer_context(self, customer_name: str) -> dict:
        customer = await self.get_customer_by_name(customer_name)

        if not customer:
            raise ValueError(f"No customer found for name: {customer_name}")

        customer_id = get_column(customer, "id")

        if customer_id is None:
            raise ValueError(f"No customer id found for customer: {customer_name}")

        customer_id = int(customer_id)

        open_issues, recent_activity = await asyncio.gather(
            self.get_open_issues(customer_id),
            self.get_recent_issue_activity(customer_id),
        )

        return {
            "customer": customer,
            "open_issues": open_issues,
            "recent_activity": recent_activity,
        }
    async def query_postgres(self, sql: str) -> list[dict]:
        return await query_postgres(sql)
