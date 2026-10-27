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

## V2.1 — Self-steering development and human-approved Research Engine development

Goal:
Make the Developer Console self-steering across bounded development steps so the user can operate primarily inside the Console without external prompt/result handoffs, then enable workspace-bound human-approved source development in world-os-research-engine while preserving explicit approval, SHA guards, backups, rollback, no autonomous Git writes, and no autonomous database or Supabase writes.

First objective:
Make Console determine and present the next safe development action after investigation, patch preparation, review, apply, and validation, with a single human-controlled Continue safely action.

Safety boundaries:

- explicit human approval remains mandatory,
- approved source apply remains SHA-guarded and reversible,
- no autonomous Git writes,
- no autonomous database or Supabase writes,
- world-os-web remains READ_ONLY until explicitly changed,
- Research Engine source writes remain disabled until workspace-bound apply is implemented and verified.

---

### V2.1 verified state ? 2026-10-07

Completed integration outcomes:

- Developer Console has a dedicated Research execution section.
- Development orchestration and Research Engine execution remain separate.
- Research Engine executes in its own workspace and Python runtime.
- Objective-only autonomous Research Engine runtime is implemented.
- Read-only autonomous Research Engine CLI is implemented.
- Production discovery, HTTP and PDF source-content retrieval, model routing,
  extraction, grounding, source policy, and identity-resolution composition
  are wired.
- Cross-domain trusted research foundation covers 13 domains.
- Trusted canonical identity remains separate from discovery-facing names.
- Multi-target trusted autonomous research is implemented across the
  production domain set.
- Agriculture, Roads, Rail, Airports, Telecom, Water Infrastructure,
  Industry / Manufacturing, Logistics Facilities, Cities,
  Real Estate / Built Environment, Natural Resources, Oil & Gas,
  and PORT trusted research paths have been expanded and verified.
- PORT_CORE_V2 preserves the legacy trusted canonical identity model
  instead of generic WOS-ENTITY IDs.
- Port of Antwerp-Bruges is verified as a second autonomous PORT target
  using canonical ID WOS-PORT-BE-ANR-ZEE and parent
  WOS-AREA-BE-ANR.
- Antwerp-Bruges trusted exact-source execution is implemented through
  the official newsroom source policy.
- Antwerp-Bruges STS crane extraction is deterministically grounded so
  arrived / awaiting-installation assets are not mislabeled as
  operational / active.
- Live objective-only Port of Antwerp-Bruges research completed
  successfully in read-only mode.
- Canonical Research Engine test suite is green with 328 passed tests.
- No autonomous database or Supabase writes were introduced.

Current Research Engine milestone:

**Canonical Asset Population & World OS Web Map Integration**

Milestone status: **IN_PROGRESS**.
S1-S5: **COMPLETED**.
S6 local phase: LOCAL_VERIFIED.
S6 production phase: BLOCKED / NO-GO.
SEC-001: OPEN.

Verified local work:
- Fourteen local evidence items retained.
- Synthetic migration 00800, rollback and post-COMMIT recovery verified.
- Local authorized Research Engine-Web HTTP/HMAC integration verified.
- Five local OSM preview geometries implemented.
- Canonical production access remains disabled.

Six pending production conditions:
1. production_migration_00800_approval
2. positive_authorized_production_http_test
3. production_auth_session_and_permission_verification
4. trusted_geographic_asset_source
5. authenticated_research_engine_web_integration
6. explicit_real_data_access_approval

Geographic source candidates:
- DE-HAM: Hafen Hamburg terminal map and HPA port boundary.
- ANR-ZEE: Port of Antwerp-Bruges nautical map and Digitaal Vlaanderen GRB.
- Candidate selection does not verify coordinates, licensing or canonical identity.
- Canonical geographic publication remains disabled.

Next bounded objectives:
1. Align canonical Research Engine milestone and task evidence with Console.
2. Preserve production NO-GO until separately approved security and data gates pass.
3. Continue Research Engine orchestration, persistence, recovery and Dev Agent
   integration according to the canonical Master Roadmap.
4. Require an exact database write preview and explicit human approval before
   any canonical record insertion or real-data activation.
Safety boundaries remain unchanged:

- database and Supabase writes require explicit preview and human approval,
- no automatic Git writes,
- no git add dot,
- Research Engine execution remains read-only unless a bounded approved
  write workflow explicitly requires otherwise.

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

## Research Engine — S6 evidence synchronization (2026-10-25)

Reference: RESEARCH_ENGINE_S6_389_20261025

Active milestone: Canonical Asset Population & World OS Web Map Integration.

- S1-S5: COMPLETED.
- S6 local technical phase: LOCAL_VERIFIED.
- Production function 00800: technical state verified by S6-330, S6-335, S6-336, S6-337 and S6-341.
- Local Research Engine-Web integration: VERIFIED.
- Local SEC-001 authorization and security tests: VERIFIED.
- Five local OSM geometries: IMPLEMENTED and locally validated.
- Production operator account existence: USER CONFIRMED.
- Production JWT, active session and READ permission: not independently verified by this synchronization.
- Formal migration approval/history: not established.
- Production HTTP verification, canonical source approval and real-data release: remain gated.
- Production release: NO-GO.
- SEC-001: OPEN.
- Milestone: IN_PROGRESS.

Execution decision:
Do not repeat completed synthetic tests, migration inspection, geographic preview validation or authorization code reviews without new concrete evidence of a defect.

Resume functional Research Engine development strictly according to the canonical Master Roadmap and active milestone requirements.

Do not formally close S6 or synchronize a COMPLETED milestone state until the required release gates have passed.

## Research Engine ? S6 canonical production evidence (2026-10-27)

Active milestone: `milestone-canonical-asset-population-web-map`.

### Verified progress since 2026-10-25

- Production operator authentication, active session and canonical READ: PASS in earlier S6 execution evidence.
- Bounded Web-to-Supabase canonical READ integration: PASS; temporary HTTP activation reverted to DISABLED.
- CTA Hamburg official source registration: COMPLETED; two sources created.
- CTA canonical promotion: COMPLETED / INSERTED.
- CTA canonical entity: `WOS-ENTITY-AE8025A10747F1D0`; production READ VERIFIED.
- CTA physical asset: `PORT_TERMINAL`; production READ VERIFIED.
- CTA provenance: two PRIMARY fact-source bindings; production READ VERIFIED.
- CTA promotion execution ID: `2c602fab-f59e-4fee-9267-df0d25f0aa2e`.
- CTA promotion batch ID: `7d2c744a-9869-582c-b4e2-6fd31d5da1c1`.
- Approved manifest SHA-256: `4dbc1288541f943b3a3e8b84edb7380d3c1dec2f5fa41855b9661891f9e53e22`.

### Milestone and release boundaries

- S1-S5 remain COMPLETED; S6 remains IN_PROGRESS.
- Public Web map publication and public HTTP activation are not prerequisites for Research Engine technical completion.
- Production public release remains NO-GO; public HTTP activation remains DISABLED.
- SEC-001 remains OPEN pending reconciliation of applicable technical and authorization completion gates.
- CTA geographic boundary is not approved or published.
- No further CTA source registration or canonical promotion is required for this verified record.
- Milestone closure and final Dev Agent Console synchronization remain pending.
- Existing release-gate documents retain their historical evidence; newer verified results supersede outdated PENDING descriptions only within their proven scope.
- No automatic Git, database, deployment or public publication actions are authorized by this roadmap update.
