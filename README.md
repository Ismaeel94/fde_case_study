# fde_case_study

## Setup Instructions

1. Clone the repository from GitHub:

   ```bash
   git clone https://github.com/Ismaeel94/fde_case_study.git
   ```

2. Start the application using Docker Compose:

   ```bash
   docker compose up
   ```

   Some containers, particularly Keycloak, may take 2–4 minutes to start up.

3. Access the application in the browser:

   ```text
   http://localhost:8000/
   ```

4. Authentication is triggered through Keycloak when the application is accessed. The application uses Keycloak's default login page.

5. Keycloak is exposed on:

   ```text
   http://localhost:8080/
   ```

6. The following users are configured in both the database and the Keycloak realm:

| Username | Password | Access |
|---|---|---|
| `admin_user` | `admin` | Create issues, update issues, read access |
| `support_user` | `support` | Update issues, read access |
| `sales_user` | `sales` | Read-only access |

---

## Architecture Overview

The solution consists of:

- FastAPI application hosting the LangGraph orchestration layer and Gradio UI
- Keycloak providing authentication and role-based access control
- PostgreSQL acting as the durable system of record
- Redis providing session storage, workflow checkpointing and caching
- PostgreSQL MCP server exposing database tools to the agent
- LangSmith providing tracing, observability and evaluation support

User requests enter through the UI, are authenticated via Keycloak, and are routed through the LangGraph orchestration layer. Depending on the identified intent, requests may invoke specialised workflows or a general-purpose agent. Data is retrieved from PostgreSQL through MCP tools, application state is maintained in Redis, and responses are synthesised before being returned to the user. LangSmith captures execution traces, tool calls, latency metrics and errors for observability.

---

## Agents and Tools

The application is structured as a LangGraph workflow with multiple nodes performing varying levels of agentic reasoning.

The graph begins by identifying user intents and decomposing or rewriting queries for each intent. Each intent is then executed by its own flow, which may run in parallel, before the results are synthesised into a final response. The supported intents can broadly be classified into general queries and specific workflows.

### General Agent

For general queries, the graph includes a `langgraph.prebuilt` ReAct agent with access to PostgreSQL MCP read-only tools.

Tool calls are selected dynamically by the agent under constrained prompts. This node is responsible for handling general queries that do not fall into one of the more specific workflows.

### Specific Workflows

The graph also supports the following specific actions:

- Create an issue
- Update an issue
- Generate a customer escalation summary

The Customer Escalation Summary workflow is implemented as a LangGraph subgraph, making it a structured and reusable skill-like workflow.

### Key Design Decisions

- For known use cases, agentic autonomy is bounded by explicit graph logic to maintain control over non-deterministic behaviour.
- Fully autonomous agents, such as the general agent, have read-only access to prevent unsafe database writes.
- Database writes are performed only after authorisation checks and human-in-the-loop approval.
- Agents provide structured parameters which are then programmatically written to the database.
- LLM generations based on database reads use structured outputs and explicit evidence derived from retrieved data to reduce hallucinations.

Collectively, these decisions limit agent autonomy to areas where it provides value while retaining deterministic control over business-critical operations. The aim is to improve reliability, auditability and safety without removing the benefits of LLM-driven reasoning.

---

## MCP

A lightweight MCP server, `openmcpserver/mcp-postgres`, is used to expose PostgreSQL data to the LangGraph agent through a standard tool interface.

The primary benefit of MCP is that it decouples the agent from the underlying data source. Rather than implementing database-specific tool wrappers directly within the application, an MCP server exposes data access capabilities through a standard interface.

This separates tool definitions from the agent implementation itself: the MCP server defines and exposes the available tools, while the agent consumes them. The application can discover these tools and make them available to the agent while remaining largely agnostic to how the underlying system is implemented.

This approach makes the architecture more modular and extensible. In this prototype, if PostgreSQL were later replaced or supplemented with another system such as Salesforce or Jira, the application could integrate with the new source through the same MCP interface rather than requiring a bespoke integration.

In this prototype, MCP is used for read-only operations such as issue retrieval and issue history summaries. Write operations are intentionally implemented separately using `asyncpg`, allowing authorisation checks and human-in-the-loop approval workflows to be enforced before any database changes are made.

---

## Skills

The Customer Escalation Summary skill has been implemented as a LangGraph subgraph.

It follows a sequential series of nodes with branching logic based on information availability. The reason for modelling this as a structured workflow is that it gives greater control over the execution of each step and makes branching logic explicit for auditability.

The "Agentic_Design" diagram in the repository shows the steps involved in this skill.

---

## Authentication and Authorisation

Authentication and authorisation are implemented using Keycloak with OIDC.

Authentication takes place through Keycloak's default login page, which triggers the OIDC flow with the FastAPI backend. Once the ID and access claims are resolved, the backend constructs a server-side session and stores it in Redis. A browser cookie stores the session identifier for communication between the client and server.

I chose a server-side session model backed by Redis rather than storing authentication state entirely within browser JWTs. This allows sessions to be invalidated immediately on logout and gives the application greater control over session lifecycle management. Since Redis was already a required component of the solution, using it as the session store was a natural architectural fit.

Role-based access control is enforced for sensitive operations:

- `sales_user`: read-only access
- `support_user`: read and update access
- `admin_user`: create issues, update issues and read access

---

## Containerisation

The solution is dockerised using Docker Compose. The compose stack includes the following services:

- Application container: `support_assistant_app`
- Redis
- PostgreSQL
- PostgreSQL MCP server
- Keycloak
- `postgres-mcp-proxy` using nginx

Docker Compose provides the network bridge for internal communication between services and allows the full solution to run locally with a single command.

### PostgreSQL MCP Proxy

The `postgres-mcp-proxy` service was added because the `openmcpserver/mcp-postgres` image only accepts requests from `localhost`. This caused requests to be rejected once the setup was moved into Docker.

An nginx reverse proxy is therefore used to rewrite the `Host` header before forwarding requests to the MCP server.

---

## Database

PostgreSQL is used as the durable store for structured data. The database is seeded with representative sample data to demonstrate the main agent capabilities.

The schema includes the following tables:

- `customers`
- `issues`
- `issue_updates`
- `next_actions`
- `users`

---

## Redis

Redis is used for the following purposes:

- Session storage
- LangGraph checkpoint memory
- Application-level caches for frequently accessed data, including customers and users

PostgreSQL is used as the durable system of record, while Redis is used for operational state requiring low-latency access. Session data, workflow checkpoints and caches do not require the relational guarantees of PostgreSQL and are therefore better suited to Redis.

Redis also supports TTL and flexible key-value access, which makes it suitable for transient application state and cached lookup data.

As an auditability feature, some parts of Redis-backed memory could be persisted to PostgreSQL for long-term storage. These could include user login/logout times and LangGraph orchestration flows, including human-in-the-loop decisions. Due to time constraints, I did not implement this auditability layer in the prototype.

---

## Evaluation and Observability

Observability is addressed through LangSmith integration, which captures the trace of each agentic execution, including tool calls, latency and errors.

At the application level, logging has also been implemented to track general code flow and operational behaviour.

Evaluation was conducted using an automated Python script which called the FastAPI endpoint for the agentic application. An evaluation set of 9 test cases was assembled with the help of AI, detailing the query, expected behaviour, outputs and key concerns.

The results are summarised in:

```text
app/eval/eval_results/eval_results.md
```

For each test case, the corresponding LangSmith trace URL is also included.

---

## AI Usage
Included in separate deliverable file AI_Usage.md