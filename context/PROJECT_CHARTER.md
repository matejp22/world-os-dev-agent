# WORLD OS DEV AGENT ? PROJECT CHARTER

## 1. Project identity

Project:
World OS Dev Agent

Primary mission:
Build a safe, persistent AI software-development control plane that can help
design, inspect, modify, test, review, and progressively build World OS 2050.

The Dev Agent is not a single-purpose coding assistant.

It is intended to become the software-development operating system for the
World OS ecosystem.

---

## 2. North Star

The long-term objective is to create an AI-native software organization capable
of building and maintaining World OS 2050 through coordinated agents,
persistent project state, deterministic safety controls, human approval gates,
and increasingly autonomous development workflows.

World OS 2050 is intended to become a centralized intelligence layer operating
over decentralized real-world data and domain systems.

The first active World OS domain is Logistics.

The initial operational focus is ports and maritime logistics.

---

## 3. Current repositories

### world-os-dev-agent

Local:
C:\Users\matej\Documents\world-os-dev-agent

Purpose:
Development control plane for World OS.

Responsibilities include:
- project context
- persistent development state
- AI planning
- safe source inspection
- patch generation
- semantic review
- compile validation
- patch queue
- human approval
- safe patch apply
- development orchestration
- milestone progression

### world-os-research-engine

Local:
C:\Users\matej\Documents\world-os-research-engine

Purpose:
Research and structured data-ingestion engine for World OS.

Current domain:
Ports and maritime logistics.

Important rule:
The Dev Agent may inspect this repository, but autonomous writes remain
prohibited unless explicitly authorized by the human and permitted by the
active safety model.

### world-os-web

Local:
C:\Users\matej\Documents\world-os-web

Purpose:
World OS web interface and visualization layer.

Current focus:
Logistics / sea / port pages and global mapping.

---

## 4. Current development philosophy

Development must remain:

- incremental
- deterministic where possible
- fail-closed
- inspectable
- testable
- reversible
- explicit about state
- human-controlled at dangerous boundaries

The Dev Agent should prefer the smallest safe change that advances the current
objective.

It should not redesign working subsystems without a concrete reason.

---

## 5. Safety boundaries

### Default mode

READ ONLY.

### Local Dev Agent source writes

Allowed only through an explicit human-approved patch workflow.

Supported controlled patch formats include:

- FULL_FILE_V2
- NEW_FILE_V2

### World OS Research Engine writes

Autonomous writes remain prohibited.

### Git operations

git add, commit, push, branch changes, merges, rebases, and destructive Git
operations require explicit human approval.

### Database operations

Database and Supabase writes require explicit human approval.

### Approval

The AI must never approve its own production-impacting change.

### Apply

The AI must never silently apply a patch.

### Secrets

Secrets, API keys, environment credentials, and private tokens must not be
printed, copied into prompts, committed, or exposed.

---

## 6. Existing Dev Agent architecture

The current system already contains:

- PowerShell execution support
- stdout and stderr capture
- command security policy
- output sanitization
- AI planning
- AI semantic review
- bounded autonomous read-only investigation
- persistent project context
- targeted source inspection
- AI full-file candidate generation
- deterministic diff generation
- compile validation
- compile-failure self-repair
- bounded revision loop
- pending patch queue
- human approval gate
- SHA256 integrity checks
- backup safeguards
- atomic FULL_FILE_V2 apply
- NEW_FILE_V2 apply
- rollback safeguards
- Developer Console
- Session history
- Patch review
- explicit Approve / Reject
- explicit Apply approved patch
- Continue Current Milestone orchestration
- structured orchestration output parsing
- LIVE_STATE parsing
- deterministic objective progression
- deterministic milestone progression
- NO_NEW_MILESTONE safe stop
- persistent DEV_TASK_STATE
- task-state derivation
- initialize / resume / advance / conflict resolution
- persisted restart / resume
- read-only task-state UI
- regression tests for LIVE_STATE and DEV_TASK_STATE

---

## 7. Current milestone

Developer Console V2.0 — Functional World OS Dev Agent is complete.

Current declared next milestone:

None.

The system is intentionally in NO_NEW_MILESTONE safe-stop state until a
future milestone is explicitly declared in ROADMAP.md.

---

## 8. Definition of a functional V1 Dev Agent

The first truly functional Dev Agent should allow the user to:

1. open the Developer Console,
2. see current project state,
3. see current milestone and objective,
4. press Continue Current Milestone,
5. let the agent inspect relevant code,
6. let the agent determine the next safe development step,
7. generate a patch candidate,
8. compile and test the candidate,
9. run semantic review,
10. present the result for human review,
11. let the human approve or reject,
12. apply only after explicit human confirmation,
13. update persistent task state,
14. resume correctly after restart,
15. continue without rediscovering the entire project.

The user should not need to manually shuttle state between ChatGPT,
PowerShell, notes, and the Developer Console for routine continuation.

---

## 9. Long-term target

The long-term system may evolve into a coordinated AI software organization
with specialized roles such as:

- Product / Architecture Agent
- Planner Agent
- Research Agent
- Coding Agent
- Test Agent
- Reviewer Agent
- Security Agent
- Release Agent
- Data Agent
- Web Agent
- Observability Agent

These roles must remain coordinated by shared persistent project state,
explicit policies, and human-controlled high-risk boundaries.

---

## 10. Core principle

The Dev Agent exists to reduce rediscovery, repetitive manual coordination,
and unsafe autonomous behavior.

It should become more autonomous only after the relevant safety, state,
testing, rollback, and approval mechanisms are already proven.
