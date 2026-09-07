# WORLD OS WEB - PROJECT STATE

## 1. Repository identity

Repository:

world-os-web

Local path:

C:\Users\matej\Documents\world-os-web

Role inside World OS:

Primary human-facing visualization, exploration, intelligence, and later
operational control interface for World OS 2050.

The Web application is not a database administration panel.

It is the user interface to the World OS digital model of the physical world.

---

## 2. Product mission

The World OS frontend should allow a human operator to move through the
system conceptually as:

WORLD
->
DOMAIN
->
NETWORK
->
ENTITY
->
ASSET
->
METRIC
->
SOURCE / EVIDENCE

AI should remain available throughout this journey as an analytical,
research, and navigation layer.

The UI should expose not only what World OS knows, but also why the system
believes it.

---

## 3. Core frontend principle

The central product principle is:

THE MAP IS THE PRIMARY INTERFACE TO THE WORLD.

The first screen should not be dominated by:

- tables
- forms
- database records
- administration controls

Instead, the user begins with the world and drills into structured physical
entities and their relationships.

World OS Web should feel like an interface to a digital twin of the physical
world.

---

## 4. Long-term information architecture

The intended high-level navigation is approximately:

WORLD OS

GLOBAL

DOMAINS

Logistics
- Sea
- Rail
- Road
- Air

Energy
Water
Food
Industry
Resources
Infrastructure
Population
Economy
Environment

INTELLIGENCE

Explorer
Network
Compare
Forecasts
Alerts

AI SYSTEM

Agents
Research Queue
Validation
Approvals
Conflicts

DATA

Sources
Coverage
Quality
Imports

SYSTEM

Activity
Costs
API
Settings

This is a long-term information architecture.

Do not attempt to build all modules at once.

---

## 5. Initial frontend MVP

The intended first meaningful frontend MVP is limited to:

1. Global Map
2. Ports Explorer
3. Port Detail / Port Digital Twin
4. Sources and Provenance
5. AI Agent Activity
6. Global Search / AI

The initial Logistics / Ports frontend should consume the same World OS
business concepts used by the Research Engine and PORT_CORE_V2.

Relevant data families include:

- Port_Master
- Port_Areas
- Terminals
- Terminal_Detail
- Assets
- Connectivity
- Expansion_Projects
- Port_Metrics
- Sources
- Evidence_Links

The Web repository should not invent a parallel domain model.

---

## 6. Visual language

World OS Web should be:

- dark-first
- low decoration
- high information density
- high-tech without becoming decorative science fiction
- restrained
- infrastructure-oriented
- mission-control-like

The design direction is conceptually similar to:

Bloomberg Terminal
+
Palantir
+
modern GIS
+
mission control

but cleaner and more spatially focused.

Preferred visual characteristics:

- near-black / graphite surfaces
- thin borders
- subdued UI chrome
- large important numbers
- monospaced text for IDs and technical system data
- normal sans-serif for primary UI
- minimal use of bright color

Status colors should be functional and restrained.

Examples:

green:
verified / healthy

yellow:
warning / pending

red:
conflict / failure

blue:
active / researching

Do not turn the frontend into a colorful consumer dashboard.

---

## 7. Global Map vision

The Global Map is the center of the product.

The user should eventually be able to see:

- ports
- terminals
- shipping routes
- logistics networks
- infrastructure layers
- status
- throughput
- alerts
- confidence
- AI activity

For the Sea domain, port nodes can eventually represent metrics such as TEU
through:

- size
- visual emphasis
- labels
- filters

Potential filters include:

- geography
- year
- throughput
- operator
- draft
- automation
- data quality
- confidence

The map should scale from an initial small set of ports to global coverage.

---

## 8. Port Digital Twin concept

Selecting a port should navigate into a Port Digital Twin.

Conceptually:

PORT OF HAMBURG

[ OVERVIEW ]
[ TERMINALS ]
[ ASSETS ]
[ METRICS ]
[ CONNECTIVITY ]
[ PROJECTS ]
[ SOURCES ]
[ HISTORY ]

The page should eventually surface:

- container throughput
- vessel calls
- modal share
- draft
- terminals
- assets
- infrastructure
- connectivity
- projects
- sources
- confidence
- historical metrics

The Digital Twin should reflect the World OS object graph rather than a
flattened Excel-style record.

---

## 9. Provenance UX

One of the most important World OS frontend capabilities is provenance.

A metric such as:

8.3M TEU

should eventually be inspectable through a chain conceptually equivalent to:

value
->
period
->
source
->
URL / document
->
retrieved_at
->
agent
->
confidence
->
approval
->
history

This is a major product differentiator.

The frontend should let the operator understand why a value is trusted.

Provenance must not be hidden behind an internal-only developer interface.

---

## 10. Network Explorer vision

World OS should eventually allow graph exploration across physical objects.

Example:

Port
->
Terminal
->
Railway
->
Road
->
Warehouse
->
Factory
->
Energy
->
City

The purpose is to expose the physical-world graph and dependencies.

This is one of the transitions that turns World OS from a port dashboard into
a broader physical-world operating system.

---

## 11. AI Command Center vision

The frontend should eventually expose AI operations clearly.

Conceptual states include:

- RESEARCHING
- VALIDATING
- WAITING APPROVAL
- FAILED
- IDLE

The operator should be able to inspect:

- current agent activity
- candidate records
- validation status
- approvals
- failures
- discovered sources
- conflicts
- costs
- coverage gained
- autonomous-mode state

Important:

AI autonomy must remain visible.

The UI must not hide agent actions or production writes behind attractive
visualization.

---

## 12. Global Intelligence vision

A later World OS interface should support natural-language questions such as:

Show the 20 largest European container ports by 2025 TEU.

The response should not be limited to text.

It should be able to generate views such as:

- map
- table
- chart
- source list
- comparison
- filters

Follow-up analysis might include:

- fastest-growing ports
- ports above a given draft
- potential bottlenecks
- regional comparisons
- source-backed forecasts

This is a later phase, not the immediate implementation target.

---

## 13. Current technical stack

The current World OS Web project uses:

- Next.js
- React
- TypeScript
- Tailwind CSS
- App Router
- MapLibre GL

The map component is:

src/components/GlobalMap.tsx

MapLibre worker assets have previously been placed under:

public/maplibre/

Known worker-related files include concepts equivalent to:

maplibre-gl-shared.mjs
maplibre worker module

Do not replace the existing map stack without first inspecting the current
repository and confirming a real need.

---

## 14. Map design work already completed

The initial Global Map was iterated several times.

Important completed design direction:

- map renders successfully
- MapLibre is functioning
- the visual style was changed toward a darker, less colorful, more high-tech
  World OS aesthetic
- port nodes are displayed on the map
- alignment issues in surrounding UI were previously corrected

There was also a historical UI issue involving the final "Mapped" status
alignment.

That should be treated as previously resolved unless the current repository
shows otherwise.

Do not restart map styling from scratch.

---

## 15. Port route architecture - COMPLETE BASELINE

The main Port Digital Twin route is:

/logistics/sea/[port]

Example:

/logistics/sea/hamburg

Existing port subroutes include:

/logistics/sea/[port]/assets

/logistics/sea/[port]/connectivity

/logistics/sea/[port]/metrics

/logistics/sea/[port]/projects

/logistics/sea/[port]/sources

/logistics/sea/[port]/terminals

Corresponding page files exist under:

src/app/logistics/sea/[port]/

Known files include:

src/app/logistics/sea/[port]/page.tsx

src/app/logistics/sea/[port]/assets/page.tsx

src/app/logistics/sea/[port]/connectivity/page.tsx

src/app/logistics/sea/[port]/metrics/page.tsx

src/app/logistics/sea/[port]/projects/page.tsx

src/app/logistics/sea/[port]/sources/page.tsx

src/app/logistics/sea/[port]/terminals/page.tsx

This route structure is already established.

Do not create a second incompatible Port Detail routing architecture.

---

## 16. Current map port set

The development map currently contains at least the initial ports:

Rotterdam

Antwerp-Bruges

Hamburg

Valencia

These are development / initial visualization nodes.

Do not assume this is the final canonical port list.

The backend / Research Engine remains authoritative for trusted World OS data.

---

## 17. Port slugs - COMPLETE

Each initial map port was updated to include a route slug.

Recorded mappings:

Rotterdam:
rotterdam

Antwerp-Bruges:
antwerp-bruges

Hamburg:
hamburg

Valencia:
valencia

The slug is used to connect Global Map interaction with the Port Digital Twin
route.

This work was confirmed completed before the latest handoff.

---

## 18. Exact current development position

CURRENT WORLD OS WEB MILESTONE:

Connect Global Map port nodes to existing Port Digital Twin routes.

The last confirmed completed action was:

Add slug to all four initial port objects in:

src/components/GlobalMap.tsx

The exact next step was:

Add a click handler to each port marker.

Target behavior:

click Hamburg marker
->
navigate to
/logistics/sea/hamburg

The intended implementation around the marker element is conceptually:

markerElement.style.cursor = "pointer";

markerElement.addEventListener("click", () => {
    window.location.href = `/logistics/sea/${port.slug}`;
});

Then create the MapLibre marker.

This exact click behavior was the next unconfirmed step.

Do not assume it has already been implemented until current repository source
is inspected.

---

## 19. Exact next verification

When resuming World OS Web development, inspect:

src/components/GlobalMap.tsx

Determine whether the marker click handler already exists.

If it does not exist:

implement the smallest change required to navigate to:

/logistics/sea/${port.slug}

Then test:

Hamburg marker
->
/logistics/sea/hamburg

Do not redesign the map during this step.

Do not change route architecture during this step.

---

## 20. Web development principles

### Inspect before modification

Repository source is authoritative.

The handoff records the last known state but does not override actual code.

### Small slices

Change one bounded UI capability at a time.

### Reuse existing routes

Do not duplicate routes or create alternative Port Digital Twin paths.

### Backend alignment

Frontend entities and routes should eventually align with canonical World OS
identity and data contracts.

### No fabricated production data

Development fixtures are acceptable when clearly identified.

Do not present invented values as canonical World OS facts.

### Provenance-first design

Important metrics should eventually link back to their evidence.

### Scale-aware architecture

Design components so they can later support:

- millions of entities
- very large metric histories
- global map layers
- many AI agents

without redesigning the core information architecture.

---

## 21. Repository safety boundaries

The Dev Agent may inspect:

C:\Users\matej\Documents\world-os-web

Default cross-repository behavior:

READ ONLY.

Do not autonomously:

- modify World OS Web source
- install or remove packages
- change Next.js configuration
- replace MapLibre
- change environment variables
- git add
- git commit
- git push
- delete files
- modify production deployment configuration

Any source write must go through the active human-approved Dev Agent workflow.

---

## 22. Relationship to Research Engine

world-os-web and world-os-research-engine are separate repositories with
different responsibilities.

Research Engine:

discovers, extracts, normalizes, validates, resolves, and prepares World OS
data.

Web:

visualizes and exposes World OS state to human operators.

The frontend must not become a second research engine.

The Research Engine must not become a UI application.

Their shared contract is the canonical World OS model and its APIs/data
interfaces.

---

## 23. Relationship to World OS Dev Agent

world-os-dev-agent is the development control plane.

Its future role is to safely:

- inspect world-os-web
- understand current Web milestone
- generate a bounded candidate
- compile/test
- present diff
- require human approval
- apply safely
- persist development state
- resume later without rediscovery

The Dev Agent does not gain autonomous Web write permission merely because
WEB_STATE.md exists.

---

## 24. Web roadmap from current checkpoint

### Phase 1 - current

Complete:

Global Map port node
->
Port Digital Twin navigation.

Verify Hamburg first.

### Phase 2

Make the main Port Digital Twin route a stable shell.

Expected concerns:

- port identity
- header
- tabs
- route consistency
- loading/error behavior

Use existing routes.

### Phase 3

Connect child sections:

- terminals
- assets
- metrics
- connectivity
- projects
- sources

Initially focus on correct information architecture before complex
visualization.

### Phase 4

Build provenance UX.

Important values should be inspectable back to:

- source
- evidence
- confidence
- retrieval/validation history

### Phase 5

Connect frontend to canonical World OS backend/API rather than maintaining
static local fixtures.

Repository/API contracts must be inspected at that stage.

### Phase 6

Add Ports Explorer and filtering.

Potential dimensions include:

- TEU
- year
- geography
- operator
- draft
- confidence
- status

### Phase 7

Build AI Agent Activity / Command Center.

Expose:

- research
- validation
- approval
- conflicts
- failures
- cost
- coverage
- autonomous state

### Phase 8

Build Network Explorer.

Visualize relationships across the World Object Graph.

### Phase 9

Build Global Search / Global Intelligence.

Natural-language request
->
structured World OS view.

### Phase 10

Expand from Logistics / Sea into additional World OS domains.

Do not implement domain expansion before the Logistics interaction model is
stable.

---

## 25. Non-negotiable Web invariants

A future Dev Agent must preserve:

1. The map remains a primary World OS interaction surface.

2. World OS Web is not merely a database admin dashboard.

3. Existing Port Digital Twin routes are reused.

4. Production data is not fabricated.

5. Provenance is a first-class UX concept.

6. AI autonomy remains visible to human operators.

7. Human approval boundaries are not hidden by the UI.

8. Research logic remains in the Research Engine.

9. Web source writes require human-approved Dev Agent workflow.

10. Git operations require human approval.

11. Repository source remains authoritative over handoff assumptions.

12. Small deterministic development slices are preferred.

---

## 26. Immediate handoff

Repository:

world-os-web

Local path:

C:\Users\matej\Documents\world-os-web

Last confirmed completed Web change:

Initial map ports contain routing slugs.

Current milestone:

Global Map -> Port Digital Twin navigation.

Exact next inspection:

src/components/GlobalMap.tsx

Exact next objective:

Confirm whether the port marker click handler already exists.

If absent, add the smallest handler that navigates:

/logistics/sea/${port.slug}

First verification target:

Hamburg

Expected route:

/logistics/sea/hamburg

Write permission:

NO - inspect current repository first.
