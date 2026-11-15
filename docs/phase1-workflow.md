# Phase 1: The Agentic Workflow

**Superseded by `docs/plan.md`.** This early draft assumed GitHub Issues and Projects as the ticket store. The system now uses Jira, with different statuses, agents, and rules. It is kept for history only.

Status: draft for review. Nothing here is implemented beyond the shell.

## 1. What the workflow does

A piece of work moves from an idea to a merged pull request. Agents do the structured steps. People make the judgment calls and approve anything that changes production or is large.

```
idea ─► Product ─► Staff ─► [human approves] ─► Dev ─► QA ─► [human merges] ─► done
            │         │                          │       │
            │         ├─ spike needed ──► (spike ticket, human or agent)
            │         ├─ infra needed ──► (human for now; Cloud Dev later)
            │         └─ unclear ──────► needs-human
            │                                    └─ fails 2x ─► needs-human
```

The first slice is Product → Staff → one Product Dev → QA, plus the two human gates. The other agents keep their contracts in this document but are not built yet.

## 2. Shared source of truth

Work lives on the tracker, not in agent memory. Each linked board (GitHub Project or Jira board) and repo is the record. The agents read and write only through the tracker and the repo.

- **Ticket** = one GitHub Issue (or Jira issue). One ticket maps to one PR.
- **Status** = a single-select field on the board. It is the only field that drives routing.
- **Exceptions** = labels, not statuses, so the main path stays short.
- **Claims** = an `agent:<role>` label set by the agent when it starts work. A ticket with an `agent:*` label is locked to that agent.
- **Handoffs** = a structured comment (section 5) posted at the end of every agent run.

The contracts below are written against this model, so Jira can be a second provider later with the same statuses mapped onto its workflow.

### Status flow

| Status | Meaning | Set by |
|---|---|---|
| `Inbox` | Idea recorded, not yet refined | Human or intake |
| `Refining` | Product or Staff agent is working on it | Agent claim |
| `Ready` | Refined and planned; waiting for a human | Staff agent |
| `Approved` | Human approved it for development | **Human gate G1** |
| `In Dev` | Dev agent is working; branch open | Dev agent |
| `In Review` | PR open; QA is running | Dev agent |
| `QA Failed` | QA found problems; dev retries | QA agent |
| `Ready to Merge` | QA passed; waiting for a human | QA agent |
| `Done` | Merged | Human merges; board automation |

### Exception labels

| Label | Meaning | Who clears it |
|---|---|---|
| `needs-spike` | Requirements or approach are unknown | A human, or a spike ticket that closes |
| `needs-infra` | Work needs infrastructure changes | A human, until Cloud Dev exists |
| `needs-human` | An agent cannot decide or has hit its retry limit | A human |
| `agent-failed` | An agent run errored (tool failure, timeout) | Harness retries, then `needs-human` |
| `blocked` | Depends on another ticket | Automatic when the blocker closes |

An exception label does not change the status. A ticket can be `Refining` and `needs-spike` at once. The harness refuses to advance any ticket that carries `needs-human`.

## 3. Roles and contracts

Every agent has the same shape: a trigger, an input, an output, a list of allowed writes, and a list of failure outcomes. "Allowed writes" is enforced by the harness, not by the prompt.

### Product Agent

- **Trigger:** a ticket is created in `Inbox`.
- **Input:** the idea text in the ticket title and body.
- **Output:** the ticket body rewritten to the ticket template (section 4). Status moves to `Ready`.
- **Allowed writes:** the ticket body, labels, and status. Nothing in the repo.
- **Failure outcomes:** `needs-human` if the idea is too vague to write acceptance criteria for.

### Staff / Discovery Agent

- **Trigger:** a ticket moves to `Refining` with a Product-written body.
- **Input:** the ticket body, plus read access to the linked repo(s).
- **Output:** a technical plan appended to the ticket: the files likely to change, the approach, the test approach, a size estimate, and a `scope` list (section 6). Status moves to `Ready`.
- **Allowed writes:** the ticket, labels, and new linked spike tickets. Read-only on the repo.
- **Failure outcomes:**
  - `needs-spike` when the approach is unknown. The agent opens a spike ticket linked to this one.
  - `needs-infra` when the change touches infrastructure, CI/CD, or deploy config.
  - `needs-human` when acceptance criteria conflict or the scope is too large for one PR.

### Product Dev Agent (two instances, each on distinct tickets)

- **Trigger:** a ticket moves to `Approved` and no open PR exists for it.
- **Input:** the ticket, including the Staff plan and `scope`.
- **Output:** a branch and a PR (section 7). Status moves to `In Dev`, then `In Review` when the PR opens.
- **Allowed writes:** the branch in the linked repo, the PR, the ticket's status and labels. Never `main`. Never files outside `scope`.
- **Failure outcomes:**
  - `needs-human` if the change would exceed `scope`, if the diff passes the size limit (section 7), or if tests cannot be made to pass after its own attempts.
  - `agent-failed` on tool or sandbox errors. The harness retries the run once, then escalates.

### QA Agent

- **Trigger:** a PR moves to `In Review`.
- **Input:** the PR diff, the ticket's acceptance criteria, the repo's test commands.
- **Output:** new or updated tests on the PR branch, a QA report comment, and the outcome status.
- **Allowed writes:** test files on the PR branch, the PR comment, the ticket status.
- **Outcomes:**
  - `Ready to Merge` when all tests pass and each acceptance criterion maps to a test or is marked manual.
  - `QA Failed` when tests fail. The Dev agent gets the report and retries. After 2 failed rounds the ticket gets `needs-human`.
- **Note:** QA may not weaken or delete existing tests to make a run pass. It may only add tests or fix its own tests.

### Later agents (contracts only)

- **Perf Tester:** triggered by `Ready to Merge` on tickets labeled `perf`. Runs benchmarks. Output is a comment with numbers against a baseline. Failure is `needs-human` on regression beyond a threshold.
- **Refactor Dev:** triggered by a scheduled scan. Opens small PRs of the same shape as Dev, labeled `refactor`. Subject to the same gates.
- **Performance Optimizer:** triggered by a Perf Tester regression or a profile. Same PR shape. Must attach before/after numbers.
- **Cloud Dev:** triggered by `needs-infra`. Behind a hard gate: nothing is applied without a human approving the plan. Gets scoped, short-lived credentials only.
- **On-call:** triggered by an alert. Drafts an incident ticket and remediation plan. Never applies a fix to production without a human gate.

## 4. Ticket template

The Product Agent writes this into the issue body. Staff adds the sections marked *(Staff)*.

```markdown
## Problem
What is wrong or missing, and for whom.

## Acceptance criteria
- [ ] Each criterion is observable and testable.
- [ ] ...

## Out of scope
What this ticket deliberately does not do.

## Affected repos
- owner/name

## Plan *(Staff)*
Approach in a few sentences.

## Scope *(Staff)*
Files or directories this ticket may change. Used for overlap checks.
- path/to/dir/

## Size estimate *(Staff)*
S / M / L, with the reason.

## Test approach *(Staff)*
Which tests cover which criteria.

## Risks and open questions
```

## 5. Handoff comment

Every agent run ends with one comment in this format. It is the audit trail and the input to the next agent.

```yaml
agent: staff            # product | staff | dev | qa | ...
run_id: 2c7f...         # harness run id, for tracing
issue: 123
from_status: Refining
to_status: Ready        # unchanged if the outcome is an exception
outcome: success        # success | needs-spike | needs-infra | needs-human | agent-failed
summary: One or two sentences on what was done and why.
artifacts:
  - https://github.com/owner/repo/pull/45   # when a PR exists
```

## 6. Overlap rule (two Product Devs)

Two dev runs may proceed at once only if their `scope` lists do not overlap, and neither touches a shared file. Shared files are a fixed list per repo (for example `go.mod`, `package.json`, lockfiles, migrations, CI config), and the list is set by a human. The harness checks overlap when it assigns a ticket. If overlap exists, the second ticket waits. Merges go in order, and each PR is rebased on the latest main before QA.

## 7. PR conventions

- **Branch:** `agent/<issue>-<slug>`, for example `agent/123-search-filter`.
- **Title:** `[#123] short summary`.
- **Body:** starts with `Closes #123`, copies the acceptance criteria as a checklist, lists the files changed, and links the handoff comment.
- **One PR per ticket.** A ticket that needs two PRs is split into two tickets by Staff.
- **Size limit:** more than 400 changed lines, or more than 10 files, sends the ticket to `needs-human`. The number is a starting point to tune.
- **Commits:** one commit per attempt. QA's fixes are separate commits so the history shows what changed.
- **Never merged by an agent.** A human clicks merge.
- **Labels:** `agent-authored` on every agent PR, so reviews and metrics can filter on it.

## 8. Human gates

| Gate | Where | What the human checks | Required in first slice |
|---|---|---|---|
| G1 | `Ready` → `Approved` | The ticket's criteria, plan, and scope | Yes, for every ticket |
| G2 | `Ready to Merge` → `Done` | The PR diff and QA report | Yes, for every PR |
| G3 | `needs-infra` plan → applied | The infra plan and its blast radius | Not built yet |
| G4 | Production deploy | Release decision | Not in scope |
| G5 | Large refactor | Whether the refactor is wanted | Not built yet |

## 9. Exception paths

- **Spike needed:** Staff opens a linked spike ticket and sets `needs-spike`. The spike closes with a human-written conclusion, which Staff reads on its next run.
- **Infra change required:** `needs-infra` stops the flow. Until Cloud Dev exists, a human does the infra work and clears the label.
- **Incident:** On-call (later) opens an incident ticket. Dev agents never take incident tickets without a human approving the fix.
- **Retry limit:** two failed QA rounds mean `needs-human`.
- **Agent error:** one automatic retry, then `needs-human`. The run's trace is kept.
- **Kill switch:** a single flag stops all agent triggers. Labels stay as they are, so resuming is safe.
- **Overlap conflict:** the second ticket waits (section 6).

## 10. Decisions to confirm

1. **Status field vs. labels.** I recommend the GitHub Projects single-select field for status, with labels only for exceptions.
2. **G1 for every ticket.** I recommend yes for the first slice, then relaxing it for small tickets once acceptance rates are known.
3. **Who writes ideas.** Recommended: a human writes the idea in one line, and the Product Agent expands it.
4. **QA retry limit.** Recommended: 2.
5. **Size limit.** Recommended: 400 changed lines or 10 files.
6. **Shared-file list.** Which files in your repos should always count as shared?
7. **Jira.** Should the first slice use GitHub Issues and Projects only, with Jira boards added after it works?

## 11. Not in Phase 1

- Harness details: checkpoint policy, retries, cost and runtime limits, tracing. These are Phase 3.
- Success metrics. These are Phase 5, but the handoff comment is designed so they can be computed from it.
- Agent prompts and tool allow-lists. Those are written per agent in Phase 4.
