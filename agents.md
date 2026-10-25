You will use vibe coding (via Cursor, Codex, etc) to rapidly scaffold and deploy a custom, single-purpose AI agent. The agent can do whatever the student wants—from summarizing local PDF readings to checking their calendar and drafting emails—as long as it relies on external tools and context rather than just the LLM's base knowledge.



The Technical Requirements (The "Must-Haves"). The agent must successfully implement the following architectural components:

1. Tool Use / Skills: The agent must be equipped with at least two distinct functional skills (e.g., fetching a web page, querying a database, parsing a CSV, calling an external weather API).
2. Context Integration (MCP or similar): You must use a standardized protocol like MCP (Model Context Protocol) or standard LLM function calling to bridge the agent's brain with the local environment or APIs.
3. The "Vibe Coding" Constraint: You must use AI to write the boilerplate (e.g., the MCP server setup, the Pydantic models for function arguments, or the API request logic) so you can focus entirely on the agent's system prompt and orchestration loop.
