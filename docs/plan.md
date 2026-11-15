# Fokist agents: plan and decisions

Status as of 2026-11-14: design and agent prompts are done. Implementation happens on the Linux machine that will run everything. This file replaces `docs/phase1-workflow.md`, which described an earlier GitHub-Issues-based design.

How we work: one thread at a time. Step 0 of every phase first, then step 1, and so on. Propose and get a go-ahead before building. Keep technical detail out of the discussion unless asked.

## 1. What this is

A local, multi-agent software factory. Agents turn user stories in Jira into reviewed, tested, merged code, with the user making the decisions that matter. The orchestrator routes work by ticket status, runs agents on a local model, and records everything in SQLite. The user watches it over SSH and talks to the orchestrator as an "eng manager" (section 7).

## 2. Products, Jira, GitHub

**Products.** Fokist (ticket prefix `FKST`) and Propeller (prefix `PRPLR`, to confirm). They are independent products. Fokist reads from DynamoDB, which Propeller feeds. The DynamoDB schema is the contract between them. Each product has its own Jira board. The ticket prefix tells the harness which product a ticket belongs to. Propeller is a Rust ELT pipeline on dbt and BigQuery and has no UI.

**Jira is the system of record.** GitHub holds code and PRs. The Jira workflow was built in the Fokist project:

- Statuses: Open (entry only), Backlog, Needs refinement, In refinement, Hotfix review, Ready for dev, Dev in progress, PR open, PR in review, Ready for QA, QA approved, Merged to main, Regression testing, Deployed to prod.
- Deployed to prod is in Jira's Done category.
- The old In Progress, In Review, and Done statuses were removed.
- Transitions are in order, not "from any status":
  - Open → Backlog (Triage to backlog)
  - Backlog → Needs refinement (Send to refinement)
  - Backlog → Hotfix review (Start hotfix review)
  - Needs refinement → In refinement (Start refinement)
  - In refinement → Ready for dev (Approve for dev)
  - Hotfix review → Ready for dev (Approve hotfix)
  - Ready for dev → Dev in progress (Start development)
  - Dev in progress → PR open (Open PR)
  - PR open → PR in review (Request review)
  - PR in review → Ready for QA (Approve for QA)
  - PR in review → Dev in progress (Request changes)
  - Ready for QA → QA approved (Approve QA)
  - Ready for QA → Dev in progress (Fail QA)
  - QA approved → Merged to main (Merge to main)
  - Merged to main → Regression testing (Start regression)
  - Regression testing → Deployed to prod (Deploy to prod)
  - Regression testing → Dev in progress (Regression failed)
- All existing Fokist tickets were moved to Backlog with the `human` label.
- Labels: `human` is work for people. `ai` is work for the agents. `hotfix` marks hotfixes. Exception labels: `needs-human`, `needs-spike`, `needs-infra`, `agent-failed`, `blocked`.
- The Propeller Jira project has not been configured with this workflow yet.

**GitHub.** The org `fokist-propeller` is on the Free plan. There is no branch protection on private repos, so every merge rule is enforced by the Dev agent, not by GitHub. The "GitHub for Atlassian" app is installed and connected to the org (all repos) so Jira shows PRs and branches. Jira automation rules were declined; the harness moves ticket statuses itself.

## 3. Agents

All agents run on one shared local model (section 6). The roster:

| Agent | Serves | Role in one line |
|---|---|---|
| Product | Fokist only | Helps the user decide features and the roadmap; writes stories; can move Backlog tickets into the upcoming sprint |
| Staff | both | Technical direction, scope, spikes, decision logs, tickets from stories, assigns bots, reviews proposed tickets; no code |
| Dev | both | Implements one ticket test-first in its own branch, opens the PR, merges after both approvals |
| PR review | both | Technical and architecture review; four outcomes; checks tests for technical quality |
| QA | both | Per-ticket QA and the sprint regression; second approval |
| Performance | Fokist only | End-of-sprint experiments with Prometheus and Grafana; writes improvement tickets |
| On-call | both | Hotfixes. How this agent works is still to be decided, and its prompt isn't written. The hotfix path depends on it |
| Orchestrator ("eng manager") | all | Routes work, runs the queue, answers the user's questions (section 7) |

The full prompts are in `prompts/`.

## 4. Workflow rules

**Sprints and sizing.**
- A sprint is 5 days. Points: 1 = half a day, 2 = a day, 3 = a day and a half, 5 = two days, 8 = three days. Tickets are ideally 5 points or less.
- Each dev bot targets 12 points per sprint, with a hard maximum of 15. Work that truly can't be split may exceed 15.
- Staff splits tickets so each bot lands near 12 and keeps related tickets on the same bot, so it keeps context.
- Putting a ticket in the sprint is the approval. There is no separate approval before dev starts.
- Only the user and the Product agent move tickets from Backlog into the upcoming sprint. Nobody creates a ticket directly in a sprint.

**Tickets.**
- Written as user stories: "As a [role], I would like to [X]."
- Product, Staff, QA, Dev, and Performance can all create tickets. Every new ticket goes to Backlog. Staff recommends the order.
- Everyone can link tickets. Staff owns cross-product dependency links.
- Decision logs, spikes, design documents, roadmaps, and Performance experiment pages live in Confluence. Everyone can read and write it. Tickets link to the pages.

**Who moves statuses.** The harness does, and it checks every move against the routing table. Agents request moves. No agent can move a ticket to Deployed to prod; that follows a manual deploy by the user.

**Events.**
- Jira webhooks and the Jira poll are triggers only. The harness re-reads the issue with its changelog and records each status change once, keyed by issue key and history ID.
- The Jira poll runs hourly, but only if no webhook arrived in the last 2 hours.
- The webhook route exists but the tunnel to reach it is deferred. Polling is enough for now.
- The harness polls GitHub every 15 minutes for PR review state.
- PR review bot approved with no comments, or approved with comments that are all resolved: the harness moves the ticket to Ready for QA. The only comments allowed to stay open are explanatory comments the Dev agent left on its own code.

**Branches and PRs.**
- Each ticket gets a branch named `agent/<KEY>-<slug>`, cut from the latest main. The PR targets main, and its title includes the ticket key.
- The PR description summarizes the work and lists every acceptance criterion. Unexpected changes (scope changes, refactors made to make room) are listed in the description, and each gets an inline PR comment explaining why.
- A PR touches only the repo of its ticket's product. The Dev agent may write to any repo, but only for a ticket that belongs to that repo's product. Cross-product work gets its own linked ticket.
- A file outside the ticket's scope is a warning that QA reviews, not a block.
- Stacked PRs are the exception. The PR review bot reviews the base PR (base = main) on its own. If PRs are stacked on it, its approval comment says the base is waiting for the rest of the stack to merge down. The base is QA'd and merged to main first. The next PR is then rebased on main and becomes the base.

**Reviews.**
- The PR review bot has four outcomes: approve with no comments; approve with comments (must be fixed before QA); advisory or nitpick (Dev may resolve or dismiss with a reason); request changes (explained on the code).
- The Dev agent can request a re-review. The review bot checks whether the Dev agent's reasoning holds, then accepts it and approves, or rejects it and requests changes again.
- QA picks up a ticket only when the PR has a PR review bot approval and no open comments (except the Dev agent's explanatory ones). QA checks readiness again every time the PR changes.
- QA critiques the tests the PR adds, for intention and quality.

**Merging.**
- The Dev agent merges its own PR, and only when both the PR review bot and the QA bot have approved. Those must be separate identities, neither of them the Dev agent. It also needs zero open threads and CI passing on the head commit. If it can't read the review state, it doesn't merge.
- After approval, the Dev agent decides whether a further change is trivial. A trivial change doesn't need a new review. The Dev agent records the change and why it judged it trivial. A non-trivial change triggers a re-review request.
- Other org members can still merge by hand. GitHub doesn't prevent it.

**QA failures.**
- Per-ticket: QA requests changes on the PR, moves the ticket back to Dev in progress, and writes the bug and exact reproduction steps on both the PR and the ticket.
- Sprint regression: QA finds the ticket or tickets whose code is behind the failure, moves each back to Dev, and comments on how the change contributes to the failure.
- There is no QA-specific retry limit. The orchestrator's loop guard escalates any ticket that re-enters the same status 10 times.

**Regression and deploys.**
- Per-ticket QA checks the feature and the user's path to it. It doesn't run the full regression.
- After the sprint's tickets merge to main and dev, QA runs the full sprint regression. It gates the prod deploy.
- Dev deploys automatically on merge to main. Prod deploys by a manual GitHub Action that the user runs, once regression passes. That is a policy, not enforced by the action.

**Blockers and escalation.**
- A Dev blocker is a comment on the ticket plus the `needs-human` label. Staff or Product raises it with the user.
- A rejected tool call gets one retry with the rejection reason. A second rejection sends the ticket to `needs-human`.

**Hotfixes.**
- A ticket with the `hotfix` label goes to Hotfix review, where Product and Staff review the situation with the user. The on-call bot then picks it up from Ready for dev.
- Hotfix branches come from a `prod` branch that mirrors what's live. Sprint work never reaches it. Testing targets `prod`.
- Hotfixes skip nothing, and they take priority over all other agent work until they reach prod.
- After deploying, the hotfix merges into main with fresh PR review and QA approvals.

**Performance.**
- Dev leaves performance notes on the PR and ticket when working code could be faster. It doesn't chase performance itself.
- The Performance agent reads those notes at the end of each sprint and tests them with Prometheus and Grafana on the local copy of the app.
- It aims for at least 5% on response time, request time, or cloud billing, up to about 20%. It looks for easy wins, not big refactors.
- It publishes proven results as HTML in Confluence and writes tickets for them in Backlog. Staff judges the tickets, and the user decides what enters a sprint.

## 5. Tools

One MCP-style server per service, written by us. Every call goes through a tool gateway inside the orchestrator, which checks the caller's role, runs the write checks, writes an audit log, and forwards to the real service. The existing Atlassian MCP connection isn't used for agent writes, because it acts as the user and sits on a deprecated endpoint.

**Servers:** Jira, GitHub, Confluence, Grafana and Prometheus (read-only), BigQuery (read-only, Propeller only), a local test runner, and file tools limited to the ticket's worktree.

**Per-role access:**
- Product: Jira, Confluence.
- Staff: Jira, Confluence, GitHub read.
- Dev: GitHub on its own branch, test runner, Jira and Confluence.
- PR review: GitHub read and review.
- QA: Jira, GitHub read, comment and review, test runner.
- Performance: Grafana and Prometheus read, load-test runner, Confluence, Jira ticket creation.
- On-call: Jira, GitHub, Grafana and Prometheus read.
- Linking tickets and Confluence read and write are open to every role.

**Jira tools:** get_ticket, search_tickets (limited to the caller's product), list_transitions, add_comment, update_fields (Product and Staff), set_labels, create_ticket, link_issues, transition (requested by agents, applied by the harness).

**GitHub tools:** read_file, create_branch (name pattern and base enforced), push_commit (own branch, scanned), open_pr, get_pr, list_reviews, list_review_threads, submit_review (PR review and QA only), post_comment, reply_to_thread, resolve_thread, merge_pr (Dev only, checks the merge rule itself), get_check_runs.

**Never available to any agent:** delete, force-push, push to main, changing repo or branch settings, and removing members.

**Write checks the harness runs:**
- Product prefix must match the product.
- Text lengths are capped and scanned for secrets.
- Labels must be on an allowlist, and `ai` and `human` can't both be set.
- Branch names must match the pattern and base on current main.
- Pushed files are scanned for secrets, and CI configuration, lockfiles, and secret files are blocked unless the scope names them.
- Reviewer identity must match the role, and nobody reviews their own PR.
- `merge_pr` verifies the two approvals, open threads, and CI itself.
- Every write carries an idempotency key and an audit log entry.

## 6. Runtime on the Linux machine

**Hardware and model.**
- Arch Linux, RTX 3060 with 12 GB VRAM.
- One model for every agent, Qwen3.5 9B through Ollama on the host. One model avoids swap time on a single GPU. The 9B (about 6.6 GB) leaves room for context.
- The model is not final until the test passes (section 8, step 2). Candidates: qwen3.5:9b, qwen2.5-coder:14b, qwen3:14b.
- The DeepSeek R1 distills were dropped because they reportedly lack native tool calling in Ollama. That comes from third-party sources, so verify.
- Context is the tight spot on 12 GB. Agents read files in ranges and search, and never load a whole repo into a prompt.
- If native tool calling is unreliable, the model emits JSON validated against a schema (Ollama structured output). A malformed call gets the one retry.

**Layout.**
```
Jira / GitHub / Confluence <-- tool gateway (in orchestrator) <-- agent workers --> Ollama (GPU)
                                     ^                                  |
                          orchestrator: supervisor,                run containers
                          job queue, SQLite record               (no credentials, offline)
```
- A job queue in SQLite with leases. A worker that crashes loses its lease and the job is retried.
- Agent workers run on the host, one loop per role. They call the model and the tools, and write token use to the ledger.
- A model scheduler gives the GPU to one inference at a time and batches queued jobs by model.

**Run containers (one per run, created and removed by the runner).**
- Only the runner talks to Docker. Agents never do, and containers never get the Docker socket.
- Mounts: the ticket's git worktree, and shared Go module and build cache volumes. Nothing else from the host.
- Network: none, with one exception, a dependency step that fills the module cache. Tests then run offline.
- Hardening: non-root, all capabilities dropped, `no-new-privileges`, read-only root filesystem with tmpfs scratch, memory, CPU and process limits, and a timeout.
- Containers carry no credentials. Git pushes run on the host with the GitHub App token, after the gateway checks the diff.
- Each container is labeled with its run ID, and a reaper removes orphans at startup.
- The Fokist image adds Playwright for UI checks. The app under test and the test runner share an internal Docker network with no outside access. Test data comes from DynamoDB Local and a local libSQL server, so no cloud credentials are involved. Verify that the Fokist code can point at them.
- Propeller dry runs and dbt tests run on the host through the BigQuery tool, with a read-only service account on a dev dataset.

**Other services.**

| Service | Reached through | Notes |
|---|---|---|
| Jira, Confluence | gateway, bot token | host-side only |
| GitHub | gateway, GitHub App token | merge checks in the gateway |
| Grafana, Prometheus | gateway, read-only | Performance agent |
| BigQuery and dbt | gateway, read-only account | Propeller QA |
| Go modules | dependency step only | the one network exception |
| DynamoDB, Turso | local test stand-ins | no cloud credentials |

**Storage and secrets.**
- Everything lives under one directory such as `/var/lib/wf`: the SQLite file, worktrees, bare mirrors of the repos, caches, and the Performance agent's HTML artifacts.
- Secrets sit in a root-owned file readable only by the service user: the GitHub App key and the Jira token. No cloud model key is needed.
- Every service binds to localhost or a unix socket. Nothing is public. Never mount `~/.aws`, `~/.config`, the gcloud directory, or the keychain into a container.

**Running it.** systemd units for Ollama, the orchestrator and gateway, and workers. Timers for the two pollers.

**Arch notes.**
- A rolling release can break the NVIDIA driver after a kernel update. Use the DKMS driver, and reboot after kernel updates.
- Ollama on the host needs the NVIDIA driver and CUDA. The container toolkit is only needed if Ollama ran in Docker, which we avoid.
- Check the current Arch package names for Ollama with CUDA before installing.

**Frameworks and tracing.**
- **LangGraph is the run engine**, as decided. Each agent run is a small graph: a model call, then tool calls through the gateway, looping until the work is done or the run's step and time limits are hit. State is checkpointed to SQLite, so an interrupted run resumes. The supervisor, the gates, and the write checks are plain Python outside the graph.
- **LangChain is glue only.** `langchain-core` provides messages, tool definitions, and callbacks. `langchain-ollama` (`ChatOllama`) is the client to the local model, with tool binding and structured output. An MCP adapter exposes the gateway's tools to the graph. Routing, merge rules, and write checks stay in our own code, so they don't depend on LangChain.
- **Langfuse** runs self-hosted under Docker Compose on the Linux box, bound to localhost and viewed through an SSH port forward. Its LangChain callback handler is attached to every run, so each run becomes a trace: spans for every model call and tool call, grouped into one session per ticket key. Every trace carries the ticket key, product, agent role, run ID, and model name. Use it to read what an agent actually did, find slow or looping steps, compare the model-test candidates, and run evals later. Cost fields stay empty because the model is local.
- **The SQLite token ledger stays the source of truth** (`src/wf/usage.py`, `wf usage`). It keeps working if Langfuse is down. A single callback writes each model call to both the ledger and Langfuse.
- **Resource note.** The Langfuse stack runs several services (web, worker, Postgres, ClickHouse, Redis, object storage) and needs real RAM. Check the Linux box's RAM before installing it, and leave room for the model.
- **Verify before relying on it:** that the Langfuse LangChain callback works with the current LangGraph and `langchain-ollama` versions, that `ChatOllama` tool binding works with the chosen model, and which MCP adapter package to use.

## 7. The orchestrator as eng manager

- **Access:** `ssh` into the box, then `wf chat` inside tmux so the session survives disconnects. Nothing is public. The web dashboard is reachable through an SSH port forward.
- **Plain commands that don't use the model:** `wf status`, `wf jobs`, `wf runs`, `wf usage`, `wf tail`. They keep working when the model is busy or down.
- **Persona:** "You are the eng manager for this workflow. Answer from the lifecycle record, job queue, and token ledger. Cite ticket keys. Say when you don't know. Never move tickets, approve, or merge."
- **Reads:** the job queue, ticket histories, run output, the token audit, GPU and service health, and Jira and GitHub state through the gateway.
- **Acts, with the user's confirmation:** pause or resume one agent or all of them (kill switch), requeue a failed job, trigger a poll now.
- **Never does:** move tickets, approve or merge PRs, change sprints, or deploy.
- **GPU:** chat has priority. An agent's current model call finishes first. If the model is busy, the chat says where the user is in the queue.
- **Extra:** a morning digest of the last 24 hours, built from the lifecycle record with no model needed.

## 8. Build order for the Linux machine

Each step has a check that says it's done.

1. **Machine prep.** NVIDIA driver, Docker, Ollama, a service user, the data directory, empty systemd units. *Done when:* `nvidia-smi` works and a hello-world container runs.
2. **Model test.** The same tool-calling task on qwen3.5:9b, qwen2.5-coder:14b, and qwen3:14b. Also measure how much context fits, and whether thinking mode can be turned off. Downloading models needs the user's go-ahead. *Done when:* one model is confirmed.
3. **Run-container runner and Go image.** *Done when:* scratch-repo tests pass, and the escape checks fail as expected: no host paths, no network, no credentials, container removed after success, failure, and timeout.
4. **Tool gateway and servers.** Jira, GitHub, and Confluence first, with the write checks, audit log, and idempotency keys. Grafana, Prometheus, and BigQuery after.
5. **Agent worker loop, model scheduler, job queue, token ledger.** The loop is a LangGraph run graph using `ChatOllama` and the gateway's tools, with the ledger callback attached.
6. **Product-aware routing and the pollers.** Prefix picks the product, the product picks its agent set, the status picks the agent. Wire the Jira and GitHub pollers to dispatch.
7. **Eng-manager chat and status commands.** Built before the simulation, because it's how the first runs get watched.
8. **Langfuse.** Docker Compose on localhost, with the callback handler on every run. *Done when:* a run shows up as a trace with its spans, tagged with ticket key, product, role, and model, and `wf usage` still matches it.
9. **Playwright in the Fokist image.**
10. **Simulated workflow on a scratch repo.** Last.

## 9. Existing code

`src/wf/` carries over:
- `config.py`, `integrations.py`: linked repos and boards, and the Jira and GitHub clients.
- `events.py`: Jira intake, dedupe, and the poll rule.
- `pipeline.py`: one path from trigger to supervisor.
- `orchestrator.py`: routing table, hotfix rule, lifecycle record, kill switch, loop guard. Routes on status only today.
- `usage.py`: token ledger and audit.
- `cli.py`: `link`, `unlink`, `list`, `check`, `usage`, `route`, `kill`, `poll`.
- `web/app.py`: a small FastAPI app with `/webhooks/jira` (token in the query string, which is a known gap; signed webhooks would be better).

Superseded and safe to remove: `graph.py` (the placeholder linear graph), `runs.py`, and the runs pages in the web app. The 77 tests passed at the time of writing.

## 10. Open items

- Confirm the Propeller prefix `PRPLR`, and set up the Propeller Jira workflow.
- Create the GitHub Apps (PR review bot, QA bot, and the Dev bot's identity). Confirm that an App doesn't use a paid seat. This is unverified.
- The plan to remove other org members from GitHub is on hold. Nobody gets removed until the user says so, and the people affected should hear about it first.
- Set up the harness's Jira API token and the GitHub App credentials. None exist yet.
- Decide how the on-call agent is going to work: how it takes in incidents, what it may fix, and when it escalates. Then write its prompt. The hotfix path depends on it.
- Decide how the cross-product planning session shows up in Jira.
- Add AI instruction files to the Fokist and Propeller repos. The Dev, QA, and PR review agents read them.
- Model test result (step 2).
- The Jira webhook tunnel (ngrok or a cloud host), and signed webhooks.
- Check the Linux box's RAM and CPU, and decide whether Langfuse fits beside the model.
- Verify the LangChain, LangGraph, `langchain-ollama`, and Langfuse integration points listed in section 6.
