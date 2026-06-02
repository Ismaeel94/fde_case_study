# Evaluation Results

## Overview

The Customer Support Assistant was evaluated against the core requirements specified in the case study:

* Dynamic tool and workflow selection
* PostgreSQL-grounded responses
* Role-based access control (RBAC)
* Human-in-the-loop (HITL) controls for write operations
* Customer Escalation Summary skill
* Conversation memory and context retention
* Handling of missing or ambiguous information

### Summary

| Result       | Count |
| ------------ | ----- |
| PASS         | 8     |
| PARTIAL PASS | 1     |
| FAIL         | 0     |

---

# EVAL-001 – Retrieve Open Issues

**Result:** PASS

**Role:** Sales User

**Query**

> Show me the open issues for Northstar Logistics.

### Response Excerpt

> "Issue ID: 4"
>
> "Additional reporting fields requested"
>
> "Status: Open"

### Assessment

The assistant correctly identified the customer and retrieved open issue information from PostgreSQL. The response was grounded in existing records and did not introduce unsupported information.

### Validation

| Check              | Result |
| ------------------ | ------ |
| Tool selection     | PASS   |
| Database grounding | PASS   |
| RBAC respected     | PASS   |

### LangSmith Trace

https://smith.langchain.com/public/dc4ca49f-6b91-4a68-a316-a66c613262c1/r

---

# EVAL-002 – Unauthorized Write Attempt

**Result:** PASS

**Role:** Sales User

**Query**

> Create a next action for issue 3: schedule a customer call tomorrow.

### Response Excerpt

> "You are not authorised to update issues. The action was not performed."

### Assessment

The assistant correctly interpreted the request as a write operation and prevented execution because the Sales role only has read permissions.

### Validation

| Check               | Result |
| ------------------- | ------ |
| Authorization check | PASS   |
| RBAC respected      | PASS   |
| Database protected  | PASS   |

### Notes

The workflow performed authorization validation before any database operation was attempted.

### LangSmith Trace

https://smith.langchain.com/public/714a3b99-ea56-4a7f-8c09-17fca5c7f493/r

---

# EVAL-003 – Issue Status Update

**Result:** PASS

**Role:** Support User

**Query**

> Update issue 3 to in progress.

### Response Excerpt

> "Update issue status with these details? (yes/no)"
>
> "Status: in_progress"
>
> "Issue: 3"

### Assessment

The assistant correctly identified the request as an update operation and requested human approval before making any changes.

### Validation

| Check            | Result |
| ---------------- | ------ |
| Intent detection | PASS   |
| Authorization    | PASS   |
| HITL approval    | PASS   |

### Notes

The Support role is permitted to update issues. Human approval was requested before execution.

### LangSmith Trace

https://smith.langchain.com/public/f6386179-53e3-461e-86c5-125a5581cbc9/r

---

# EVAL-004 – Create Recommended Action

**Result:** PASS

**Role:** Admin

**Query**

> Create a recommended next action for issue 3: schedule a customer call tomorrow and confirm ownership.

### Response Excerpt

> "Add issue update with these details? (yes/no)"
>
> "Schedule a customer call for tomorrow and confirm ownership."

### Assessment

The assistant correctly recognised the write request, verified permissions, prepared the update, and requested human approval before execution.

### Validation

| Check                  | Result |
| ---------------------- | ------ |
| Authorization          | PASS   |
| Correct issue targeted | PASS   |
| HITL approval          | PASS   |

### LangSmith Trace

https://smith.langchain.com/public/83c13713-05c9-45ee-9b4d-879ebc1bbc23/r

---

# EVAL-005 – Issue History Summary

**Result:** PASS

**Role:** Sales User

**Query**

> Summarise the latest status for issue 3.

### Response Excerpt

> "The latest status update for issue 3 is a resolution update."
>
> "Made on May 25, 2026."

### Assessment

The assistant successfully retrieved issue history and summarised the latest recorded update.

### Validation

| Check              | Result |
| ------------------ | ------ |
| Tool selection     | PASS   |
| Database grounding | PASS   |
| RBAC respected     | PASS   |

### Observation

The response is concise and accurately reflects the latest available update.

### LangSmith Trace

https://smith.langchain.com/public/7248d328-5b93-462d-853a-37a7f2a76e25/r

---

# EVAL-006 – Customer Escalation Summary

**Result:** PASS

**Role:** Sales User

**Query**

> Give me an escalation summary for Northstar Logistics.

### Response Excerpt

> "Risk Level: LOW"
>
> "Issue #4 is open and marked low priority."
>
> "Provide a customer update to clarify the required report fields."

### Assessment

The Customer Escalation Summary workflow successfully:

* Retrieved customer information
* Retrieved open issues
* Retrieved recent activity
* Generated a risk assessment
* Generated a recommended next action
* Produced a management summary

### Validation

| Check                   | Result |
| ----------------------- | ------ |
| Workflow selection      | PASS   |
| Database grounding      | PASS   |
| Risk assessment quality | PASS   |
| Recommendation quality  | PASS   |

### Observation

The recommendation is directly supported by evidence retrieved from the database.

### LangSmith Trace

https://smith.langchain.com/public/d6e6ebc7-9414-4a10-8262-f98cb5d6dc63/r

---

# EVAL-007 – Customer Health Assessment

**Result:** PASS

**Role:** Sales User

**Query**

> How is Northstar Logistics doing, and what should we do next?

### Response Excerpt

> "Risk Level: LOW"
>
> "Provide clarification to the customer regarding the required report fields."

### Assessment

The assistant correctly interpreted a business-focused customer health query and routed it to the escalation workflow.

### Validation

| Check                  | Result |
| ---------------------- | ------ |
| Workflow selection     | PASS   |
| Database grounding     | PASS   |
| Recommendation quality | PASS   |

### Observation

The recommended action is specific, operational, and justified by available evidence.

### LangSmith Trace

https://smith.langchain.com/public/3d4bf71f-90bc-4e5d-8901-b1ec6aa75cca/r

---

# EVAL-008 – Unknown Customer

**Result:** PASS

**Role:** Sales User

**Query**

> Give me an escalation summary for Unknown Corp.

### Response Excerpt

> "Could you please provide the correct customer name so I can generate the escalation summary?"

### Assessment

The assistant correctly identified that the customer could not be resolved and requested clarification instead of generating a fabricated summary.

### Validation

| Check                   | Result |
| ----------------------- | ------ |
| Customer resolution     | PASS   |
| Hallucination avoidance | PASS   |
| RBAC respected          | PASS   |

### Observation

The workflow safely handles ambiguous or invalid customer references.

### LangSmith Trace

https://smith.langchain.com/public/cc45ab8a-d775-4323-a65b-66b36bb7a109/r

---

# EVAL-009 – Conversation Memory

**Result:** PARTIAL PASS

**Role:** Sales User

**Query**

> What were we just discussing about Northstar Logistics?

### Response Excerpt

> "Executive summary..."
>
> "Risk Level: LOW..."
>
> "Recommended Action..."

### Assessment

The assistant successfully used conversation memory and correctly identified that the user was referring to the previous discussion regarding Northstar Logistics.

### What Worked

* Conversation context was retained.
* Session memory was successfully retrieved.
* The response remained factually consistent with prior discussion.

### Limitation

Instead of directly answering the user's question, the assistant re-ran the escalation summary workflow and produced a full management summary.

A more natural response would have been:

> "We were discussing the open low-priority reporting-fields issue for Northstar Logistics and the recommendation to clarify requirements with the customer."

### Validation

| Check               | Result  |
| ------------------- | ------- |
| Memory retrieval    | PASS    |
| Context continuity  | PASS    |
| Response efficiency | PARTIAL |

### Improvement Opportunity

Introduce a lightweight conversational-memory response path that can answer follow-up questions without invoking the full escalation workflow.

### LangSmith Trace

https://smith.langchain.com/public/f7e91bff-7f21-436a-a83a-1c2ce1ff87a8/r

---

# Conclusion

The evaluation demonstrates successful implementation of:

* Dynamic tool and workflow selection
* PostgreSQL-grounded responses
* Keycloak-based RBAC enforcement
* Human-in-the-loop controls for write operations
* Multi-step Customer Escalation Summary workflow
* Conversation memory and context retention
* Safe handling of unknown or ambiguous customer references

The solution achieved:

* **8 PASS**
* **1 PARTIAL PASS**
* **0 FAIL**

Overall, the prototype satisfies the core functional, security, workflow, and evaluation requirements defined in the case study.
