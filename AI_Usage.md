##AI usage

I used AI tools during the development of this prototype in bounded and reviewable ways.

### Generating Code

**Tool:** Cursor

**Scope:** Project scaffolding, boilerplate code, dependency resolution, bounded automation with defined contracts and logic.

I generally used Cursor to implement specific functions, apply common patterns such as logging or tracing, and debug code.

**Review:** I reviewed generated code line by line and iterated with the model to avoid unnecessary complexity or over-engineering. In some cases, I used pytest tests to validate generated code. I also checked for key concerns such as SQL injection risks, resource leakage and consistency with the broader project structure.

### Generating Tests

**Tool:** ChatGPT

**Scope and method:** I described the purpose of the prototype and shared examples of the types of queries it should handle. I also specified the expected format of each test case and the concerns I wanted to evaluate, such as tool usage, grounding in data and role-based access control.

**Review:** I manually reviewed the generated test cases before using them.

### Generating Diagrams

**Tool:** ChatGPT

**Scope:** I described the Docker Compose stack and the LangGraph orchestration setup so that ChatGPT could help generate architecture and agentic flow diagrams.

**Review:** I manually reviewed the generated diagrams to verify consistency with the implementation.

### What I Would Not Trust AI With

I generally use AI where the requirements are clear, bounded and testable. I would not trust AI tools to make design-level decisions independently, or to make widespread changes that would be difficult to review safely.
