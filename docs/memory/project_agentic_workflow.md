<!-- Working log of decisions, copied from the assistant's memory on 2026-11-14.
     Entries were appended as the discussion went on, so a later entry overrides an earlier one.
     Older entries marked 'updated' or 'replaced' may be stale. The clean, current version is docs/plan.md.
     Personal names were replaced with roles. -->

---
name: agentic-workflow-design-decisions
description: "Settled decisions for the agentic development workflow (agents, sprint sizing, gates, stack) built in ~/agentic-workflow; use before asking the user about these again"
metadata:
  node_type: memory
  type: project
  originSessionId: 624dd2d2-bf1d-414a-88e6-4c7f8fc97a8b
  modified: 2026-11-14T18:23:46.009Z
---

Agentic dev workflow (Phase 1 contracts being defined one agent at a time, user answers questions as we go; user does NOT want documents, only questions).

**Stack:** Python. LangGraph (official) for the workflow; FastAPI + Jinja + htmx + Alpine.js for the web app. Project at ~/agentic-workflow. No Go in this project.

**Product Agent:** takes ideas from the user, helps the user refine tickets, triages incoming tickets (bugs), and works with the user to plan the next sprint. It places a bug into a sprint ONLY when the user prioritizes it. The user decides which tickets go into the next sprint. It does not choose sprint contents on its own.

**Sprint sizing:** a sprint is 5 days. Each dev bot has a soft target of 12 points per sprint and a hard maximum of 15 (user: 12 is a rule of thumb, a little over is fine, never near 24). Scale: 1 pt = 0.5 day, 2 = 1 day, 3 = 1.5 days, 5 = 2 days, 8 = 3 days. Tickets ideally <= 5 points. Note: 12 points = 6 days of work by this scale, one day over a 5-day week.

**Staff repo access:** Staff can always write to the repo, and it reviews PRs. Its reviews are one of three kinds: blocking change, advisory or nitpick, or approval with comments to handle.

**Dev Agent (DevBot):** writes unit tests for new behavior, or updates existing tests for changed behavior. Writes acceptance tests for each ticket's criteria. Acceptance criteria are written during refinement by the user, Product, and Staff. When a blocker or scope increase comes up, the bot opens a blocker ticket and stops. The user, Product, and Staff decide it together, the ticket is closed with the decision, and the bot resumes on the updated ticket. Uses the `needs-human` label for these.

**QA Agent:** checks (1) the code meets the ticket's intention, (2) it meets the acceptance criteria, (3) regression: existing behavior still works. Writes regression tests that carry forward into future acceptance criteria. Probes edge cases. Checks scope flexibly: scope may grow or shrink if justified, and QA checks the bot's justification. A scope change is discussed by the Dev bot with Staff and Product, and left as a note for QA. The user has the final say on scope increases that matter.

**PR size:** no fixed line or file limit. PR size is an effect of how the work is decomposed. Staff, Product, and the user decide what gets done. DevBot decides how. Layered work (scaffolding, state or API wiring, front end) that needs to be separated becomes its own ticket. DevBot works in vertical slices, single-threaded per ticket, like knitting a sweater, not layer by layer like building a house. The earlier 400-line / 10-file proposal is dropped.

**Trackers (changed):** Jira is the system of record for tickets: work is done in Jira. PRs go to GitHub. Jira and GitHub stay in sync so Jira shows ticket state and links to PRs. QA reads acceptance criteria only from Jira tickets. This replaces the earlier plan of GitHub Issues + GitHub Projects as the ticket store.

**Ticket status list (confirmed by user, Jira is the tracker):** 1 Backlog → 2 Needs refinement → 3 In refinement → 4 Ready for dev (available to pick up) → 5 Dev in progress → 6 PR open → 7 PR in review (PR review bot) → 8 Ready for QA (only after PR review bot approval AND no open comments) → 9 QA approved → 10 Merged to main (auto-merge, deploys to dev env) → 11 Regression testing → 12 Deployed to prod. Jira statuses follow PR state where a PR exists (PR open/merged read from GitHub). In dev = merged and deployed to dev env.

**Merge:** automatic. Branches merge to main on their own once they have two approvals.
- **PR review bot (approval 1):** reads the ticket, understands intention and requirements, checks technical implementation, acceptance criteria, and test quality. Gives approval.
- **QA bot (approval 2):** runs only on tickets that already have PR review bot approval (so QA never tests code Dev is still reworking). Tests the feature, plus minor regression limited to code paths the ticket touches. Larger regression suites run separately.

**Performance Agent (new):** picks up tickets deployed to prod in the last sprint, and recommends code changes; recommendations go into the backlog as tickets. Writes its own tests. Measures with Grafana and Prometheus. Runs locally for now: load-tests a local copy of the app on a dedicated performance branch.
Trigger: once at the end of each sprint. Reviews the whole feature a ticket belongs to (not just the latest ticket). Forms hypotheses from past performance; if no baseline exists, benchmarks first. Writes an HTML report of hypotheses, results, and experiments, and tracks experiments on its own Jira board. Creates a backlog ticket only for a meaningful improvement that doesn't need a large refactor. Meaningful = at least 5% on response time, request time, or cloud billing; during experiments it tries to maximize the gain. Each backlog ticket is discussed in refinement so it fits the roadmap and product intent. Staff agent maintains the cloud-services and billing document the Performance Agent uses.

**Local lifecycle record:** the whole workflow runs on a local machine, so each ticket's lifecycle is recorded locally in SQLite (LangGraph checkpoints also use SQLite).

**PR review bot comment types:** blocking (must fix before approval), advisory or nitpick (Dev bot decides based on its other work: it can fix, or reply that it won't and resolve), approval with comments (approved, but the comments must be resolved before QA picks up the ticket; QA checks that they are resolved).

**Staff agent:** no longer reviews PRs. It keeps ticket planning, refinement, objections, and ticket assignment.

**Triggers:** agents are triggered by ticket status. Jira pushes status changes by webhook, and the harness also polls Jira hourly as a fallback. Webhook exposure (ngrok or a cloud host) is deferred. The harness must process each status change once.

**Regression and deploys:** QA's minor regression covers only the user's path to the feature, step by step, plus the pages along it. The full sprint regression runs before a prod deploy. Dev deploy: automatic on merge to main. Prod deploy: manual GitHub Action, run by the user whenever they choose, only after regression passes (a policy, not enforced by the action).

**Hotfix path:** a ticket with the `hotfix` label (a label, not a status) is handled by the dedicated on-call bot, which writes the fix. Hotfixes skip nothing: they get the same PR review bot and QA approvals. Priority: a hotfix preempts any agent's open work (tickets, PRs, QA) until it reaches prod. Hotfix review stage (before work starts): Product and Staff review the situation so the fix keeps the app's intention and technical design; the user contributes; then the ticket moves to Ready for dev, and the on-call bot picks it up. Hotfix tickets use the normal statuses after Ready for dev. Their testing and PRs target the `prod` branch. A `prod` branch mirrors what's live: hotfix branches come from `prod`, and sprint work never reaches it. After deploy to prod, the hotfix merges into `main` with fresh PR review bot and QA approvals (not reused), so it stays in the next release and is checked against the code in motion.

**Event intake (built in ~/agentic-workflow/src/wf/events.py):** webhooks and the hourly poll are triggers only. On either, the issue is re-read from the Jira REST API with expand=changelog, and each status change is stored once, keyed by (issue key, history id). The webhook payload's changelog is never trusted. The poll runs only when no webhook has arrived in 2 hours. The user chose a deterministic key over AI comparison. Webhook route is /webhooks/jira, gated by WF_WEBHOOK_TOKEN (fails closed when unset). Known gap: the token travels in the query string. Not yet verified against a live Jira instance.

**Later (on the plan, not now):** run Langfuse (self-hosted AI observability) for trace UI on top of the local token ledger in src/wf/usage.py. The ledger stays the local record.

**Build approach (user-chosen):** iterate through the study-guide phases. Lay the foundation, work through each phase, then go back and bring each earlier phase up to where it should end up. Tool allow-lists wait until the orchestrator pattern is chosen and the MCP servers exist.

**Runtime:** one machine, no Kubernetes. Each agent has its own isolated environment to code in (per-agent git worktree, plus containers for running code and tests). Langfuse runs under Docker Compose. Open question: whether dev test containers get internet access.

**Coordination (user chose supervisor):** a supervisor routes each status change by a fixed table (no model call), in src/wf/orchestrator.py. Hotfix label reroutes dev work to the on-call agent. Every decision goes to the local lifecycle table. Kill switch (`wf kill on|off`) halts dispatch. Loop guard escalates a status re-entered 10 times. Agents are not built; dispatch is an injected callable that does nothing by default. Not yet wired: the webhook and poll do not call the supervisor. The placeholder LangGraph run graph and the web runs pages are superseded and not yet removed.

**Products:** Fokist (ticket prefix FKST) and Propeller (prefix PRPLR, to confirm). Independent products. Fokist reads from DynamoDB, which Propeller feeds: DynamoDB is the adapter and the coordination boundary (its schema and meaning are the contract). Both products share one Jira board, but each gets its own board. The prefix routes a ticket to its product; status then picks the agent. Propeller moves more slowly.

**Propeller agents (updated):** the Dev agent replaces the Data Engineer; it handles both products. Staff Data Engineer and Data QA remain. Data QA runs BigQuery dry runs. Propeller is a Rust ELT, event-driven pipeline on BigQuery. Data QA has its own prompt, with no product tests: it writes BigQuery tests and runs dry runs to keep changes cheap and verify they work. Open: whether Propeller tickets also use the generic PR review bot, on-call, and performance agents.

**Agent map by product (confirmed):**
- Fokist (FKST): Product, Staff, Dev (Product Dev bots), PR review bot, QA, Performance (sprint end), On-call.
- Propeller (PRPLR): Staff Data Engineer, Data Engineer (dev), Data QA (BigQuery tests and dry runs of dbt migrations before they reach BigQuery), its own PR review bot, On-call. No performance agent.
Both share one GitHub org. Propeller's Rust ELT pipeline, dbt, and BigQuery are the stack.

**TODO (deferred):** make the bots and supervisor product-aware. Route on (product from ticket prefix, status), so a PRPLR ticket in Ready for dev goes to the Data Engineer and an FKST ticket goes to a Fokist dev bot. Current orchestrator (src/wf/orchestrator.py) routes on status only.

**Cross-product planning (new workflow):** a discussion between the Fokist PM (Product), the Staff Data Engineer, the Fokist Staff engineer, and the user. It decides which features to build and how the data pipeline supports them. Open: how it's represented in Jira (epic or status) and whether its outcome creates linked child tickets on each product's board.

**Build order (user's rule, strict):** single-threaded. Do step 0 of every phase, then step 1 of every phase, then step 2, and so on, until the software factory is complete. Keep technical detail out of the conversation unless asked. Do not build ahead of the current step.

**Jira (done):** the 13 workflow statuses were added to the FKST project's Task workflow via the browser (the MCP connection can't edit workflows). Existing Open, In Progress, In Review, Done were kept. The new statuses are in the To Do category, so Deployed to prod does not count as done in Jira reports; not yet decided. The workflow applies to Epic, Subtask, Feature, Task, Story, Bug.

**Jira labels (done):** all 28 existing FKST tickets moved to Backlog with the `human` label. The `ai` label means work for our agentic AIs. No ai-labeled tickets exist yet; new tickets get `ai` when the agents create them. Four tickets (FKST-7, 12, 13, 16) that were AI product features were relabeled `human`.

**Local AI (decided by user):** the agent models will run locally on the user's machine, not only through a cloud API. The workflow runs fully local (orchestrator, containers, SQLite record). Model choice and runtime (e.g. Ollama, llama.cpp) still open. Token ledger in src/wf/usage.py still applies, now counting local model calls.

**Local models (updated, decided):** one model for every agent, Qwen3.5 9B via Ollama on the Linux home machine (RTX 3060 12 GB, Arch). One model avoids GPU swap cost; the 9B (~6.6 GB default pull) leaves VRAM for context. Replaces the earlier DeepSeek-Coder-V2-Lite / DeepSeek-R1 14B plan (R1 distills reportedly lack native tool calling in Ollama; sources are third-party). Pending test before committing: run the same short tool-calling task on qwen3.5:9b, qwen2.5-coder:14b, and qwen3:14b, compare success rate and time, and check whether Qwen3.5 thinking mode can be turned off. Nothing downloaded yet; pulls need user go-ahead.

**GitHub seats (pending, do NOT act yet):** the fokist-propeller org has 3 members. User plans: write to GitHub via a custom server; if 3 seats, remove everyone except the user and add the dev agent and QA agent. Not done. Open: org is on Free (no per-seat billing); seats matter only on Team. Two-approval rule needs distinct identities (PR review bot and QA bot, both distinct from the dev bot). Removing the other org members is outward-facing; confirm first.

**Tool layout (agreed):** one MCP server per service, written by us (Jira, GitHub, Grafana/Prometheus, BigQuery), so writes go through the harness and bot identities. Per-role access: Product = Jira r/w; Staff = Jira r/w + GitHub read; Dev = GitHub r/w on its own branch + local test runner; PR review = GitHub read + review; QA = Jira read + GitHub read/comment + local test runner; Performance = Grafana/Prometheus read + local load-test runner; On-call = Jira + GitHub + Grafana/Prometheus read. BigQuery server for Propeller agents only. Existing Atlassian MCP not used for writes (acts as the user; deprecated endpoint).

**Merge rule (decided, free plan):** no branch protection (Free plan). The Dev bot merges its PR only when it sees: approvals from the PR review bot AND the QA bot (distinct identities, neither is the dev bot), both on the current head commit (stale approvals don't count), and zero unresolved comments. If it can't read the review state, it doesn't merge. Other members can still merge manually; the rule is enforced by the bot, not GitHub.

**Linking (decided):** every role can link tickets and issues (Performance links improvement tickets to the feature ticket; Dev and QA link related bugs). Staff additionally owns cross-product dependency links.

**Rejected writes (decided):** a rejected tool call gets one retry, with the rejection reason returned to the agent. A second rejection sends the ticket to needs-human.

**Out-of-scope files (decided):** a file outside the ticket's scope is a warning, not a block. The agent keeps working, and QA reviews flagged files. Hard blocks stay for secrets, other products' repos, and main.

**Blockers (updated):** when the Dev agent hits a blocker, it comments on the ticket (problem, what it tried, options) and sets needs-human. Staff or Product reads it and brings it to the user. This replaces the earlier rule of opening a separate blocker ticket.

**PR content and product boundary (updated):** the PR description summarizes the work and lists each acceptance criterion. Unexpected changes (scope changes, refactors needed to make room) are listed in the description, and each one gets an inline PR comment on the changed block explaining why. The Dev agent can write to any repo, but only for a ticket that belongs to that repo's product. A PR touches only the repo of its ticket's product. Cross-product work gets its own ticket in the other product, linked via link_issues. (Confirmed by user.)

**Three shared bots (decided):** Staff, Dev, and QA serve both products. The Staff bot replaces the Staff Data Engineer, the Dev bot replaces the Data Engineer, and the QA bot replaces Data QA (BigQuery dry runs and tests are part of QA for Propeller tickets). Product-specific rules come from the ticket's product prefix.

**PR review bot (decided):** one bot for all products. Its sole focus is technical implementation, judged against the ticket's intention and the product as a whole. It flags conflicts between the ticket's scope and the product's overall scope.

**On-call (decided):** one on-call bot serves both products. Product-specific rules come from the ticket's prefix.

**QA bot, two functions (decided):** (1) Per-ticket QA: test the feature against the ticket's intention and acceptance criteria, and check that nothing broke along the path the feature was built on. That's good enough for this stage. (2) Sprint regression: after the sprint's tickets are merged into dev, run a full regression to confirm that everything merged into main, dev, and prod works together and breaks nothing that already worked. Sprint regression gates the prod deploy.

**QA intake gate (decided):** the QA agent picks up a ticket and its PR only when the PR has (1) an approval from the PR review bot and (2) every comment resolved. The only comments allowed to stay open are explanatory comments the Dev agent left on its own code.

**QA failure routing (decided):** if any part of a ticket fails per-ticket QA, QA requests changes on the PR and moves the ticket back to the Dev lane (Fail QA transition: Ready for QA to Dev in progress). It writes the bug and reproduction steps in both the PR and the ticket so Dev can reproduce and fix it. No QA-specific retry limit (dropped as redundant); the generic orchestrator loop guard (10 re-entries of the same status) is the safety net. Sprint regression failure: QA identifies the ticket(s) whose code is behind the failure, moves each back to Dev, and comments on how that change contributes to the failure.

**Stacked PRs (decided):** the PR review bot reviews the base PR (base = main) as its own unit. If it's approved and PRs are stacked on it, the approval comment says the base is waiting for the rest of the stack to merge down into it. The base is then QA'd, merged to main, and deployed to dev. Each higher PR is reviewed when it becomes the base.

**PR review bot focus (decided):** main goal is technical proficiency and architecture. It reviews tests for technical quality and intention. It does not check acceptance criteria or product fit; that's QA's job and the product owner's. It isn't a QA or product reviewer.

**Ticket creation (decided):** Product, Staff, QA, Dev, and Performance can all create tickets. Every new ticket goes to Backlog. Staff recommends the order. The user approves and moves tickets from Backlog into the sprint.

**Dev performance notes (decided):** the Dev agent doesn't chase performance. When code works correctly but could be faster, it writes a note in the PR description and on the ticket: where it is, the likely gain, and why it wasn't changed. The Performance agent reads these notes after the work reaches prod.

**Staff and decision logs (decided):** decision logs and spikes live in Confluence documents that tickets reference. Staff does spikes and decision logs to sort out future work that doesn't have tickets yet. The Product Manager and the user agree on a feature intention, and Staff creates the technical tickets that satisfy it. Tickets are written as user stories ("As a [role], I would like to [X]"), and Staff works out the technical path.

**Confluence server (decided):** add a Confluence MCP server. Every role can read from it. Writes: Staff for decision logs and spikes (write-access for others still open).

**Confluence access (decided):** every role can read and write Confluence. **Staff (decided):** does not write code or scaffolding to repos. Writes spikes, decision logs, and design documents in Confluence. Reviews proposed tickets from the user, QA, Product, and the Performance agent. Sets technical direction for the org and shapes the tickets for the next sprint.

**Product agent (decided):** serves Fokist only. It can move tickets from Backlog into the upcoming sprint, but it never creates a ticket directly in a sprint. Any Propeller change it identifies goes to the user and Staff to decide.

**Performance definition and scope (decided):** Performance covers less data sent server to client, faster responses (response and request time), better code (Big O, data structures), leaner DTOs, models, view models, endpoints, and contracts, and any reduction in resource use. Priority: hot path and last sprint's features. The agent may explore other parts of the app on its own once those are in good shape and no other work remains. Fokist only.

**Performance recommendations (decided):** may recommend restructuring files, such as lazy or eager loading, or consolidating the JS sent to the client. Anything is on the table as long as it yields a better-architected, more performant, and cheaper-to-run app in the cloud.

**Re-review after changes (decided by user):** the Dev agent judges whether a change after approval needs another review. If a nitpick, advisory, or non-blocking comment leads it into work beyond that comment's intention, the Dev agent must request a re-review. (Conflict with merge rule still open: merge requires approvals on the current head commit.)

**Merge rule (amended):** the Dev agent merges only after both approvals (PR review bot and QA bot). Trivial changes after approval don't need a new review; the approvals stand. The Dev agent decides triviality, records the change and its reason in the PR, and CI must pass on the head commit. Non-trivial changes trigger a re-review request. QA always checks PR readiness, including after trivial changes.

**PR-to-QA automation (decided):** the local harness polls GitHub for PR review state and moves tickets itself (no GitHub Action, token stays local). Approved with no comments: move to Ready for QA. Approved with comments: move to Ready for QA once all comments are resolved, except explanatory Dev comments on its own code. Polling interval: every 15 minutes.

**Resolved items (decided):** (1) Stacked PR merge order: base PR merges to main first; the next PR is rebased on main and becomes the base, then goes through review and QA. (2) Product-aware routing: ticket key prefix selects the product; the product selects its agent set; status selects the agent within that set. Implementation pending. (3) Headless browser for Fokist UI checks: Playwright runner inside the Fokist run container (agreed by user).

**Bot assignment:** Staff groups related tickets onto the same bot so it keeps context. Staff splits tickets so each bot lands near 12. The 15-point maximum is a rule of thumb: indivisible work that must finish in the sprint may exceed it.

**Gates:** G1 is replaced: putting a ticket in the sprint IS the approval, so no separate per-ticket approval before dev starts. Human merges every PR (G2, not yet confirmed). Recommended QA retry limit: 2 (not yet confirmed). Human writes ideas as one-liners.

**Status:** Jira workflow statuses (mapping to the flow: Refining, Ready, In Dev, In Review, QA Failed, Ready to Merge, Done) — not yet confirmed; exception labels (needs-spike, needs-infra, needs-human, agent-failed, blocked).

**Staff Agent:** floating technical role. Works with the user and Product Agent on implementation and infrastructure; objects to tickets and proposes sequencing (prerequisites); confers with dev bots at any point, including mid-ticket. Has full control over ticket text, labels, plans, dependencies and assignment (which bot gets which ticket; bots can also take free work). Its objections are advisory: only the user can override a Staff decision. Sprint membership stays with the user.

**Still open as of this note:** PR size limit (proposed 400 lines / 10 files), GitHub-only vs GitHub+Jira first (proposed GitHub first), shared-file list per repo, shared-file list per repo (still open), Dev-bot conflicts when two bots touch related code (covered by Staff's grouping rule). Phase 1 agents reviewed one at a time: Product, Staff, Dev, QA (all discussed; remaining details above).

**Why:** user is deliberate about the design and wants to decide each agent in turn; they were frustrated when I built code before agreeing the design. See [[feedback_propose_before_building]].
