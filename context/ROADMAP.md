# WORLD OS DEV AGENT ? ROADMAP

## Current position

V0.9:
COMPLETE

Persistent task and handoff state is implemented and verified.

Current handoff target:

V1.0 ? persistent orchestration integration.

---

## V1.0 ? Persistent orchestration integration

Goal:
Connect persistent task state to Continue Current Milestone.

Required outcomes:

- Continue Current Milestone reads resolved persistent state.
- RESUME_PERSISTED continues the persisted milestone.
- ADVANCE_FROM_LIVE_STATE is handled explicitly and safely.
- CONFLICT blocks orchestration.
- NO_NEW_MILESTONE stops safely.
- orchestration does not rediscover completed work unnecessarily.
- no automatic Git, database, approval, or patch apply actions.
- end-to-end Developer Console restart/resume is verified.

Definition of done:

User can restart the Dev Agent and continue from persisted project state
without manually reconstructing the milestone or objective.

---

## V1.1 ? State transition automation

Goal:
Reduce manual PowerShell state-management steps.

Required outcomes:

- successful objective completion produces a proposed state transition,
- state transition is validated,
- human can confirm the transition,
- LIVE_STATE and DEV_TASK_STATE remain consistent,
- failed or conflicting transitions fail closed.

---

## V1.2 ? One-button development loop

Goal:
Make Continue Current Milestone execute the normal development loop.

Target flow:

Continue
? inspect
? plan
? patch
? compile
? test
? semantic review
? queue
? human review
? apply
? regression
? state transition

Manual PowerShell should no longer be required for routine development flow.

---

## V1.3 ? Repository workspace awareness

Goal:
Make the Dev Agent explicitly aware of multiple World OS repositories.

Required outcomes:

- repository registry,
- repository-specific policies,
- repository-specific write permissions,
- clear active-repository selection,
- safe read-only cross-repository inspection.

Initial repositories:

- world-os-dev-agent
- world-os-research-engine
- world-os-web

---

## V1.4 ? Git workflow integration

Goal:
Add safe human-approved Git workflows.

Required outcomes:

- explicit changed-file list,
- diff review,
- human-approved git add with explicit paths,
- human-approved commit,
- human-approved push,
- no git add dot,
- no autonomous destructive Git operations.

---

## V1.5 ? Test and CI awareness

Goal:
Allow the agent to reason from a stable project test matrix.

Required outcomes:

- repository test registry,
- focused test selection,
- regression test selection,
- compile checks,
- CI result awareness,
- fail-closed release readiness.

---

## V2.0 ? Functional World OS Dev Agent

Definition:

The user can operate primarily through the Developer Console.

The agent can:

- understand project mission,
- load persistent state,
- identify the correct next objective,
- inspect code,
- prepare changes,
- test changes,
- semantically review changes,
- queue changes,
- accept human approval,
- safely apply approved changes,
- update development state,
- resume after restart,
- work across registered repositories under policy.

This is the first version that should be considered a genuinely functional
World OS Dev Agent.

---

## Later phases

### V2.x
- stronger repository orchestration
- test agents
- release preparation
- state history
- richer observability

### V3.x
- specialized agent roles
- task decomposition
- inter-agent handoff
- model routing
- cost controls

### V4.x
- multi-agent software organization
- controlled autonomous development cycles
- production release governance
- cross-domain World OS development

---

## North Star

Build an AI-native software organization capable of continuously developing
World OS 2050 while remaining safe, stateful, inspectable, testable, and under
human control at critical boundaries.
