# fokist-agents

A local multi-agent software factory for Fokist and Propeller.

## Intention

Turn user stories in Jira into reviewed, tested, merged code, with AI agents doing the structured work and a person making the decisions that matter. Everything runs on one machine at home, on a local model. The goal is a steady flow of small, well-tested changes that keep the products moving, without paying per token and without sending code to a cloud model.

The person stays in charge of direction: what goes into a sprint, what ships to production, and any call the agents can't settle on their own.

## How it works

- **Jira is the system of record.** A ticket's status says which agent owns it. The orchestrator routes each status change to that agent, using a fixed table, not a model call.
- **Agents are small and focused.** Product, Staff, Dev, PR review, QA, Performance, and On-call each have a prompt in `prompts/`, a limited set of tools, and one handoff format.
- **One local model serves every agent** (Qwen3.5 9B through Ollama, pending a test), on a machine with an RTX 3060.
- **Code runs in per-run containers.** Each run gets a fresh, offline container with only the ticket's worktree mounted and no credentials. Every call to Jira, GitHub, and Confluence goes through a tool gateway that checks the caller's role and the write.
- **GitHub holds code and PRs.** The Dev agent merges only after both the PR review bot and the QA bot approve.
- **Everything is recorded locally** in SQLite: the ticket lifecycle, the job queue, and every model call's token use.
- **You talk to the orchestrator** over SSH, as an "eng manager" that reports on the state of things.

## Where things live

| Path | What's there |
|---|---|
| `docs/plan.md` | The full plan: decisions, workflow rules, runtime design, build order, open items. **Start here.** |
| `prompts/` | The system prompts for each agent. |
| `docs/memory/` | A raw working log of decisions. Later entries override earlier ones. `docs/plan.md` is the clean version. |
| `docs/phase1-workflow.md` | An early draft, superseded by the plan. |
| `src/wf/` | The orchestrator code: config, Jira intake, supervisor routing, token ledger, CLI, and a small web app. |
| `tests/` | The test suite. |

## Status

- **Done:** the design, the agent prompts, the Jira workflow, and the first orchestrator pieces (intake, routing, kill switch, token ledger).
- **Next:** implementation on the Linux machine, in the order given in section 8 of `docs/plan.md`.
- **Not written yet:** the On-call agent. How it works is still to be decided.
- No agent runs yet.

## Getting started

Needs Python 3.11 or newer.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest
```

A few commands exist already:

```bash
wf list                      # linked repos and boards
wf route "Ready for dev"     # which agent owns a status
wf usage                     # token use per agent
wf kill status               # whether dispatch is halted
```

Credentials are never stored in this repo. The Jira token and the GitHub App key belong in a root-owned file on the machine that runs the system.

## How we work

One thread at a time: step 0 of every phase, then step 1, and so on. Propose and get a go-ahead before building. Keep the discussion at the level of decisions, and leave technical detail for when it's asked for.
