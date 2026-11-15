<!-- Working log of decisions, copied from the assistant's memory on 2026-11-14.
     Entries were appended as the discussion went on, so a later entry overrides an earlier one.
     Older entries marked 'updated' or 'replaced' may be stale. The clean, current version is docs/plan.md.
     Personal names were replaced with roles. -->

---
name: propose-before-building
description: "Don't start writing code for a new project or shell when the user has only discussed a plan; propose and wait for a go-ahead"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 624dd2d2-bf1d-414a-88e6-4c7f8fc97a8b
  modified: 2026-11-14T17:42:15.101Z
---

When the user is discussing a design or plan (e.g. the agentic workflow study guide), do not start creating directories, installing packages, or writing code. Lay out the proposed build and wait for an explicit "build it".

**Why:** In the agentic-workflow session I scaffolded a full project (venv, LangGraph graph, CLI, tests) after the user had only agreed on scope. They had said "lets plan" and then a scope decision; they stopped me with "i didnt say to start building this."

**How to apply:** Treat "we can do X", "let's make a shell", or agreeing to a scope as input to a plan, not a go-ahead. Confirm the location and the first deliverable before creating anything. Read-only exploration of the user's code is fine when asked a question about it.
