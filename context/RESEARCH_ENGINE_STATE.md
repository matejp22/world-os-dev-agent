# WORLD OS RESEARCH ENGINE - PROJECT STATE

## 1. Repository identity

Repository:
world-os-research-engine

Local path:
C:\Users\matej\Documents\world-os-research-engine

Role inside World OS:
Research, evidence acquisition, structured extraction, normalization,
entity resolution, and preparation of trusted World OS data.

The Research Engine is not intended to become a separate world model.

It feeds the shared World OS canonical data architecture.

---

## 2. World OS architectural origin

World OS 2050 is designed around a centralized intelligence layer operating
over decentralized real-world data.

The most important data is not simply documents or internet content.

The core objective is to maintain a structured representation of:

- what exists,
- where it exists,
- what state it is in,
- how objects relate,
- what evidence supports each fact,
- how confident the system is,
- how the world changes through time.

The resulting long-term structure is a World State / World Object Graph.

---

## 3. Canonical database philosophy

Primary database:

PostgreSQL

Spatial engine:

PostGIS

PostgreSQL/PostGIS is the canonical source of truth.

Specialized systems such as graph databases, vector databases, search engines,
data lakes, or time-series databases may later be derived from or synchronized
with the canonical PostgreSQL state.

They are not the primary identity authority.

---

## 4. Core World OS data model

The foundational model separates:

OBJECT
from
OBSERVATION / CLAIM
from
CANONICAL STATE.

The central entity is:

core.world_objects

Every significant real-world entity may become a World Object.

Examples:

- PORT
- PORT_AREA
- TERMINAL
- BERTH
- ANCHORAGE
- FAIRWAY
- WAREHOUSE
- RAIL_TERMINAL
- ROAD
- RAIL_LINE
- AIRPORT
- VESSEL
- ORGANIZATION

The same architecture is intended to expand beyond logistics to entities such
as:

- POWER_PLANT
- DATA_CENTER
- MINE
- DAM
- HOSPITAL
- FACTORY

---

## 5. Identity model

Each World Object has two identities.

### Internal database identity

UUID

Used internally by PostgreSQL relationships and references.

### Public World OS identity

WOS_ID

Example:

WOS-PORT-000000001

The WOS_ID is the persistent human-readable World OS identifier.

External identifiers such as UN/LOCODE, OSM, Wikidata, national identifiers,
or operator-specific identifiers never replace the World OS master identity.

They are mappings to the World Object.

---

## 6. Core entities

The foundational architecture contains concepts equivalent to:

### core.world_objects

Canonical identity of real-world objects.

### core.object_types

World Object ontology.

### core.object_names

Canonical names, aliases, official names, local names, historical names, and
abbreviations.

### core.external_identifiers

Mappings from a World Object to external identity namespaces.

### core.geometries

Spatial representation including:

- CENTER_POINT
- BOUNDARY
- FOOTPRINT
- ROUTE
- ACCESS
- ENTRANCE
- ANCHORAGE

### core.attribute_definitions

Definitions of relatively stable object properties.

### core.object_attributes

Canonical object properties.

Examples:

- maximum draft
- quay length
- terminal area
- rail connected
- road connected
- number of cranes
- storage area

### core.relationship_types

Definitions of graph relations.

### core.relationships

Connections between World Objects.

Examples:

- PART_OF
- HAS_PART
- LOCATED_IN
- CONTAINS
- OPERATED_BY
- OPERATES
- OWNED_BY
- OWNS
- CONNECTED_TO
- SERVES
- DEPENDS_ON
- SUPPORTS

---

## 7. Evidence and provenance model

A major World OS principle is:

Never treat a discovered statement as canonical truth merely because it was
found.

Evidence is preserved separately from canonical state.

The intended evidence flow is:

SOURCE
->
SOURCE RECORD
->
CLAIM
->
VERIFICATION
->
CANONICAL WORLD STATE

Core evidence concepts include:

### evidence.sources

Authority or origin of evidence.

Examples:

- government
- intergovernmental source
- official operator
- company
- open data
- sensor
- satellite
- academic
- manual research

### evidence.source_records

The specific retrieved document, page, record, payload, or source material.

### evidence.claims

A source's statement about a World Object.

### evidence.verifications

Evidence supporting, contradicting, or qualifying a claim.

This separation is fundamental.

Conflicting sources must be preservable without destroying earlier evidence.

---

## 8. Attribute versus metric distinction

World OS explicitly distinguishes relatively stable attributes from
time-dependent metrics.

### Attribute examples

- MAX_DRAFT
- QUAY_LENGTH
- TERMINAL_AREA
- RAIL_CONNECTED

### Metric examples

- annual TEU handled
- annual cargo tonnes
- vessel calls
- container moves
- rail modal share
- truck moves

Metrics require time and scope.

At minimum a metric concept needs:

- object
- metric definition
- value
- unit
- period
- scope
- source/evidence
- confidence

This distinction was identified as necessary before large-scale port data
collection.

---

## 9. Logistics / maritime first domain

The first active World OS domain is Logistics.

The first major object family is maritime ports.

Target hierarchy:

PORT
|-- PORT_AREA
|-- TERMINAL
|   |-- BERTH
|   |-- STORAGE
|   `-- GATE
|-- ANCHORAGE
|-- FAIRWAY
|-- ROAD_CONNECTION
`-- RAIL_CONNECTION

The purpose is not merely to create a list of ports.

The target is a structured physical and operational graph of port systems.

---

## 10. Antwerp gold-standard model

Antwerp was selected as the initial reference object for the European port
model.

Important identity rule:

Port of Antwerp is a physical PORT object.

Port of Antwerp-Bruges is a separate ORGANIZATION / managing authority.

They must not be collapsed into one physical object.

Conceptually:

Port of Antwerp
    OPERATED_BY
Port of Antwerp-Bruges

Zeebrugge is another physical port location under the same broader managing
organization.

This separation is required because physical port data such as:

- geography
- terminals
- berths
- AIS calls
- drafts
- cargo flows
- road connections
- rail connections

may have different physical scope from organization-level data.

---

## 11. Research Engine target pipeline

The long-term research pipeline is:

OFFICIAL / TRUSTED SOURCES
->
DISCOVERY
->
SOURCE POLICY
->
SOURCE SELECTION
->
RETRIEVAL
->
STRUCTURED EXTRACTION
->
NORMALIZATION
->
ENTITY RESOLUTION
->
CLAIM / CANDIDATE PREPARATION
->
VERIFICATION / POLICY
->
CANONICAL WORLD OS STATE

The Research Engine should progressively automate this pipeline.

---

## 12. Current read-only research flow

A public read-only research path has been implemented around:

research_port(...)

The established flow is:

research_port(...)
->
discovery
->
official-source policy
->
selection
->
retrieval
->
structured LLM extraction
->
DiscoveredFact

This was deliberately kept separate from uncontrolled database writes.

At the stage recorded in the development handoff, the next integration target
was the existing PORT_CORE_V2 preparation flow, while explicitly avoiding an
automatic CandidateFact / database write.

---

## 13. Research extraction architecture

The newer Research Engine direction is based on bounded extraction slices for
specific World Object child types rather than one unrestricted extraction
process.

The intent is to:

1. discover trusted evidence,
2. extract a narrow typed structure,
3. map it into the existing trusted World OS contracts,
4. validate it,
5. only later allow it to enter downstream preparation/write workflows.

This prevents a research model from inventing arbitrary database structure.

---

## 14. Port Area V0.2 - COMPLETE

The Port_Area V0.2 research extraction slice reached a green regression gate.

The following files were created for that slice:

- app/research/port_area_extraction_types.py
- app/research/port_area_extraction.py
- app/research/port_area_extraction_mapper.py
- scripts/test_port_area_extraction.py
- scripts/test_port_area_extraction_mapper.py

The slice was committed and pushed to main.

Recorded commit:

a230caf Add Port Area research extraction

This is the last explicitly confirmed completed Research Engine slice in the
handoff material.

---

## 15. Repository state at last confirmed handoff

At the last recorded checkpoint:

- Port_Area research extraction was on main.
- origin/main contained commit a230caf.
- the working tree was clean with respect to the completed development work.
- only previously known unrelated/untracked artifacts remained.
- the next planned development slice was Terminal V0.2 extraction.

Do not assume those untracked artifacts are part of the active task.

Do not delete or modify them without explicit human review.

---

## 16. Exact current development position

CURRENT RESEARCH ENGINE MILESTONE:

Terminal V0.2 research extraction slice.

The work had NOT yet proceeded to implementing the Terminal mapper.

The exact next step recorded in the handoff was to inspect the existing trusted
terminal contracts before writing any new mapper code.

Files/contracts to inspect:

### app/research/port_registry.py

Read:

TrustedTerminalProfile

and:

TRUSTED_TERMINAL_PROFILES

Purpose:

Understand the exact trusted terminal registry/profile contract.

### app/research/identity_v2_types.py

Read:

UntrustedResearchTerminalV2

Purpose:

Understand the exact untrusted research extraction type accepted by the
existing identity preparation path.

### app/importers/port_core_v2/identities_adapter.py

Read:

_prepare_terminal

Purpose:

Understand the existing preparation behavior and map into it without
duplicating or bypassing trusted logic.

---

## 17. Exact next command intent

The next Research Engine development action is READ ONLY.

It should inspect:

TrustedTerminalProfile
TRUSTED_TERMINAL_PROFILES
UntrustedResearchTerminalV2
_prepare_terminal

The objective is:

Design the smallest Terminal V0.2 extraction + mapper slice that reuses the
existing trusted terminal contracts.

Do not implement the mapper until those contracts have been inspected.

---

## 18. Terminal V0.2 expected design direction

This section describes the intended direction implied by the current
architecture, not a confirmed completed implementation.

The Terminal V0.2 slice should likely follow the Port_Area V0.2 pattern:

typed extraction model
->
research extraction
->
mapper
->
existing trusted contract
->
tests

The exact fields and mapping behavior must come from the repository's current
TrustedTerminalProfile, UntrustedResearchTerminalV2, and _prepare_terminal
contracts.

Do not invent those fields from this context document.

Repository source code remains authoritative.

---

## 19. Development principles for Research Engine work

### Reuse before duplication

Before adding research logic, inspect the existing PORT_CORE_V2 preparation
and trusted-contract code.

Do not create parallel logic when the repository already contains the required
normalization or preparation behavior.

### Typed extraction

Prefer narrow typed extraction contracts over free-form LLM output.

### Official-source preference

Official and authoritative sources should be preferred where the existing
source policy requires them.

### Provenance preservation

A research result must remain traceable to its evidence.

### Entity resolution before identity creation

Do not assume every discovered name is a new World Object.

Resolve against trusted registry / identity contracts first.

### Scope awareness

Do not transfer organization-level metrics to a physical port, terminal, or
berth unless the evidence explicitly supports that scope.

### Child-object boundaries

PORT, PORT_AREA, TERMINAL, and BERTH are separate World Objects.

Do not copy parent attributes into child objects without evidence.

---

## 20. Safety boundaries

The World OS Dev Agent may inspect world-os-research-engine.

Default cross-repository behavior is READ ONLY.

Do not autonomously:

- modify Research Engine source,
- create migrations,
- perform database writes,
- run production RPC writes,
- apply Supabase migrations,
- git add,
- git commit,
- git push,
- delete untracked files.

Any Research Engine write must pass the active human-approved development
workflow.

Database writes require explicit human authorization.

A read-only extraction or test does not imply permission for canonical data
write.

---

## 21. What the Dev Agent must remember

When the user returns to Research Engine development, do NOT restart from:

- initial World OS schema design,
- Antwerp identity modeling,
- generic research architecture,
- Port_Area extraction.

Those are historical/completed context.

Resume from:

Terminal V0.2 research extraction.

First inspect the exact trusted terminal contracts.

Then design the minimal mapper/extraction slice.

---

## 22A. Recovered detailed implementation history

The following development history is part of the canonical Research Engine
handoff.

It records concrete intermediate implementation work that occurred between the
initial architecture and the current Port_Area / Terminal extraction work.

This section exists so a future Dev Agent does not rediscover or rebuild
already completed infrastructure.

---

## 22B. Trusted port registry evolution

Research configuration was moved away from scattered hard-coded port handling
toward a trusted port registry.

Important repository concepts include:

- TrustedPortProfile
- TRUSTED_PORT_PROFILES
- get_trusted_port_profile(...)
- trusted_port_ids()
- official_source_hosts_by_port()
- exact_official_source_hosts_by_port()

Trusted research ports at the current development stage include:

Antwerp-Bruges:
WOS-PORT-BE-ANR-ZEE

Hamburg:
WOS-PORT-DE-HAM

Rotterdam:
WOS-PORT-NL-RTM

The registry is authoritative for Research Agent identity scope.

Unknown ports fail closed.

Do not invent a new canonical port because a search result contains a plausible
port name.

A prior registry refactor was committed separately before the later child
registry and Port_Area work.

---

## 22C. Rotterdam trusted research profile

Rotterdam is intentionally available as a trusted Research Agent development
port.

Trusted identity:

WOS-PORT-NL-RTM

Official name:

Port of Rotterdam

Country:

NL / Netherlands

Known aliases include forms equivalent to:

- Rotterdam
- Port Rotterdam
- Port of Rotterdam
- Rotterdam Port

Trusted official host suffix:

portofrotterdam.com

Exact trusted official host used by policy:

www.portofrotterdam.com

Trusted publisher:

Port of Rotterdam

Trusted source quality:

A

Important:

Rotterdam being in the trusted registry does NOT mean all Rotterdam child
objects or metrics are already canonical production data.

---

## 22D. Source discovery layer - COMPLETE

Source discovery was implemented as a provider abstraction separate from the
LLM provider.

Core concept:

SourceDiscoveryProvider

Implemented provider work includes:

- BraveSourceDiscoveryProvider
- SerpApiSourceDiscoveryProvider

Provider results are always UNTRUSTED input.

The provider does not decide:

- canonical source identity
- trusted publisher
- source authority
- source quality
- canonical entity identity

Those remain governed by deterministic registry/policy code.

A live read-only Rotterdam SerpApi discovery smoke succeeded with a query
equivalent to:

"Port of Rotterdam" CONTAINER_THROUGHPUT 2025 site:portofrotterdam.com

The search returned official Port of Rotterdam candidates.

The Brave integration was implemented but the live credential available at
that time returned an invalid-subscription response.

Do not treat that historical provider credential problem as an architectural
failure.

---

## 22E. Official source discovery policy - COMPLETE

Discovered sources are evaluated through deterministic official-source policy.

Important behavior:

- HTTPS is required where policy requires it.
- trusted host matching is deterministic.
- publisher trust comes from registry/policy, not from LLM inference.
- provider search output remains untrusted.
- policy may return states equivalent to:
  ELIGIBLE
  POLICY_VIOLATION
  REVIEW_REQUIRED

Source selection uses eligible policy results.

Best-source selection is bounded and deterministic.

If no eligible official source exists:

FAIL CLOSED.

Do not silently fall back to a random web result.

---

## 22F. Source content retrieval - COMPLETE BASELINE

Content retrieval is separated behind:

SourceContentProvider

Important types:

SourceContentRequest
RetrievedSourceContent

The HTTP implementation is located around:

app/research/providers/http_source_content.py

Baseline behavior includes:

- policy validation before fetch
- bounded HTTP request timeout
- redirect following
- policy validation of final URL after redirects
- redirect outside trusted official policy rejected
- HTTP error rejected
- empty response rejected
- normalized content type
- no staging
- no database write
- no canonical promotion

The runner must use the trusted normalized URL from the policy decision rather
than blindly fetching the raw candidate URL.

---

## 22G. Known retrieval technical debt

The current HTTP content layer is a safe baseline, not the final document
understanding layer.

Known unfinished work:

### HTML cleaning

The provider currently works from HTTP response text.

For HTML, a future production-quality Research Agent should extract readable
content rather than feed arbitrary raw page markup into downstream extraction.

Do not introduce a scraper rewrite without first auditing the existing
provider contract.

### PDF handling

application/pdf cannot be correctly treated as response.text.

A proper PDF content path is still required.

This is an explicit future task.

### Observed metadata

RetrievedSourceContent supports metadata such as observed title and publisher,
but the generic HTTP provider does not necessarily derive all of these fields
directly from page markup.

Discovery metadata and trusted policy metadata may currently supply some of
this context.

Preserve this distinction.

---

## 22H. Structured LLM extraction - COMPLETE BASELINE

Structured extraction was intentionally separated from deterministic
normalization.

Relevant LLM infrastructure includes concepts equivalent to:

- LLMProvider
- ModelRouter
- structured response generation
- LLMResponse provenance

Port metric raw extraction uses a typed model equivalent to:

UntrustedPortMetricExtraction

Raw extraction fields include:

- raw_entity_label
- raw_metric_label
- raw_value
- raw_unit
- raw_period
- raw_statement
- source_locator
- extraction_confidence

The LLM must NOT mint canonical values such as:

- entity_id
- source_id
- canonical_source_id
- normalized numeric value
- canonical data quality classification

Those belong to deterministic trusted code.

The purpose of the LLM is evidence extraction, not canonical truth creation.

---

## 22I. LLM provenance - COMPLETE

Extraction retains the model response metadata.

The extraction result preserves both:

- the typed raw extraction
- LLMResponse metadata

This allows later audit of:

- provider
- model
- response metadata

Do not strip LLM provenance when extending the extraction pipeline.

---

## 22J. Extraction to DiscoveredFact mapper - COMPLETE

The Research Engine contains a mapper equivalent to:

port_metric_extraction_to_discovered_fact(...)

It combines structured raw extraction with retrieved source context and
produces:

DiscoveredFact

The mapper uses information such as:

- raw entity label
- raw metric label
- raw value
- raw unit
- raw period
- raw statement
- source locator
- official final source URL
- extraction confidence
- observed title
- observed publisher
- observed content type
- LLM provider/model in extraction method

The mapper does NOT create canonical database identity.

DiscoveredFact remains research evidence, not canonical state.

---

## 22K. Target metric security guard - COMPLETE

A security/schema-fit issue was discovered during Research Agent development.

Without a target guard, a request for:

CONTAINER_THROUGHPUT

could theoretically receive an LLM extraction corresponding to another valid
catalog metric and still pass generic metric resolution.

The Research Engine was hardened so the research constraint carries the
requested target metric.

After deterministic metric resolution, the resolved metric must match the
requested target metric when one is specified.

A mismatch fails schema fit.

Conceptually:

requested:
CONTAINER_THROUGHPUT

extracted:
DRY_BULK_TONNAGE

result:
REJECT

No CandidateFact persistence.
No canonical write.

Preserve this guard.

---

## 22L. Public read-only research runner - COMPLETE BASELINE

The public research path grew incrementally.

Relevant operations now include concepts equivalent to:

research_port(...)
discover_port_sources(...)
discover_and_evaluate_port_sources(...)
discover_evaluate_and_select_port_source(...)
discover_evaluate_select_and_retrieve_port_source(...)
discover_retrieve_extract_port_metric(...)

The stable read-only metric research path is conceptually:

trusted port resolution
->
research plan
->
source discovery
->
official-source policy
->
best eligible source selection
->
redirect-safe source retrieval
->
structured LLM extraction
->
DiscoveredFact

This path does not by itself authorize staging or production writes.

---

## 22M. Read-only PORT_CORE_V2 preparation bridge - COMPLETE BASELINE

An important later integration step connected the research runner to the
existing PORT_CORE_V2 preparation architecture without persisting CandidateFact.

The runner contains a path equivalent to:

discover_retrieve_extract_prepare_port_metrics_v2(...)

Its behavior is:

1. discover/retrieve/extract a DiscoveredFact
2. deterministically prepare a CandidateFact object in memory
3. construct UntrustedResearchOfficialSource from the DiscoveredFact
4. call prepare_research_port_metrics_v2(...)
5. return the resulting read-only preparation bundle

Critical guarantee recorded in the implementation:

- CandidateFact is NOT persisted
- data is NOT staged
- no canonical write occurs

The in-memory CandidateFact is an adapter object for reusing the existing
trusted PORT_CORE_V2 preparation code.

It is not permission to call the persistent CandidateFact ingestion path.

Do not replace this bridge with a new parallel format unless the repository
contracts make that necessary.

---

## 22N. Persistent CandidateFact warning

The repository also contains an ingestion path equivalent to:

ingest_discovered_port_statistic(...)

That path can interact with CandidateFact persistence.

It must NOT be called with a live persistent repository without explicit human
approval.

The safe pre-staging workflow is the read-only preparation bridge described
above.

---

## 22O. PORT_CORE_V2 ingestion bundle compositor

The existing PORT_CORE_V2 architecture already contains a general research
bundle compositor equivalent to:

compose_research_ingestion_bundle(...)

It can combine prepared research outputs into a unified ingestion bundle.

The compositor knows categories including:

- Sources
- Port_Master
- Port_Areas
- Terminals
- Connectivity
- Assets
- Expansion_Projects
- Port_Metrics
- Terminal_Detail
- Evidence_Links

This is strategically important.

Do not create a second competing "research bundle" architecture.

New extraction slices should feed the existing PORT_CORE_V2 preparation and
ingestion bundle contracts where possible.

The research bundle is still not permission to stage or promote.

---

## 22P. Trusted child registry - COMPLETE BASELINE

Port child identity was added as a trusted fail-closed registry concept.

Confirmed trusted area examples include:

WOS-AREA-BE-ANR
Antwerp area

WOS-AREA-DE-HAM
Hamburg area

Confirmed trusted terminal examples include:

WOS-TERM-BE-ANR-MPET
MPET

WOS-TERM-DE-HAM-CTA
Hamburg CTA

The child registry tracks trusted parent relationships.

Examples:

MPET belongs to the trusted Antwerp area.

Hamburg CTA belongs to the trusted Hamburg area.

Unknown child identities fail closed.

Do not generate a canonical child WOS ID from an LLM response.

---

## 22Q. Port child entity resolution - COMPLETE BASELINE

Child entity resolution validates both label and parentage.

Confirmed regression behavior includes:

- official area label resolves
- area alias resolves
- terminal alias resolves
- untrusted area WOS ID rejected
- untrusted terminal WOS ID rejected
- unknown area fails closed
- unknown terminal fails closed
- wrong area parent rejected
- wrong terminal parent rejected
- wrong terminal label rejected

This parent-aware resolution is a core safety property.

Do not weaken it to make extraction easier.

---

## 22R. Rotterdam child objects intentionally unregistered

At the latest confirmed checkpoint:

Rotterdam itself is a trusted port.

However example Rotterdam child identities remain intentionally unregistered.

The regression contract explicitly verifies that invented Rotterdam area or
terminal identities fail closed before operator/identity registration.

Therefore:

trusted parent port
does NOT imply
trusted child object.

This distinction must remain explicit.

---

## 22S. Port_Area V0.2 extraction details - COMPLETE

Port_Area V0.2 is more than a file-presence milestone.

It has two bounded stages:

### Raw extraction

Files include:

app/research/port_area_extraction_types.py
app/research/port_area_extraction.py

Regression behavior confirms:

- raw Port_Area extraction fields accepted
- canonical child IDs excluded from LLM extraction
- optional fields handled
- extra canonical ID rejected
- typed extraction result contract enforced

### Trusted mapper

File:

app/research/port_area_extraction_mapper.py

Regression behavior confirms:

- happy path accepted
- trusted alias accepted
- wrong area name rejected
- wrong parent port rejected
- unsupported area status rejected
- missing area type rejected
- missing area status rejected

This demonstrates the intended Research Engine pattern:

untrusted typed extraction
->
trusted deterministic mapper
->
existing trusted identity contract

---

## 22T. Port_Area V0.2 regression gate

Before commit, the following related suites were green:

- Port_Area extraction
- Port_Area extraction mapper
- trusted port child registry
- port child entity resolution
- trusted port registry

The five Port_Area files were then committed and pushed.

Confirmed commit:

a230caf Add Port Area research extraction

At that checkpoint:

HEAD = main
origin/main = main
origin/HEAD = main

Known unrelated/untracked items remained:

scripts/cleanup_port_core_v2_port_metrics_canary.py
supabase/.temp/

Do not touch either autonomously.

---

## 22U. Hamburg canonical reference and research canary history

Hamburg remains a key known-good reference for PORT_CORE_V2 research and
canonical promotion behavior.

Canonical port:

WOS-PORT-DE-HAM

Official source URL:

https://www.hafen-hamburg.de/en/current/statistics/container-throughput/

Known canonical source ID:

SRC-AUTO-B6FCD1EA9C19D1DB

Metric:

CONTAINER_THROUGHPUT

Period:

2025

Unit:

TEU

Normalized value:

8300000

Raw source value:

8.3 million

Data quality:

ROUNDED

Hamburg was used to prove important properties such as:

- trusted official source classification
- deterministic source identity
- evidence binding
- port metric preparation
- policy handling
- replay/idempotency
- controlled autonomous promotion architecture

Do not replace this reference with Rotterdam until Rotterdam has passed the
same required gates.

---

## 22V. Rotterdam research validation status

Rotterdam has already been useful as the first new-port Research Agent
development target.

Read-only source discovery found the official Port of Rotterdam 2025
throughput material.

Research tests exercised Rotterdam through:

trusted plan
->
official source discovery
->
policy
->
retrieval
->
structured extraction
->
DiscoveredFact

A known research fixture/extraction uses 2025 container throughput information
around 14.2 million TEU.

However:

Rotterdam live LLM extraction and later canonical production promotion must
not be assumed complete merely because fixtures and official discovery work.

Repository/test state is authoritative.

---

## 22W. Standard PORT_CORE_V2 workbook contract

PORT_CORE_V2 remains the shared standard between manual Excel workflows and
autonomous Research Agent workflows.

The standard workbook contains visible sheets equivalent to:

README
Port_Master
Port_Areas
Terminals
Terminal_Detail
Assets
Connectivity
Expansion_Projects
Port_Metrics
Sources
Summary
Evidence_Links

Business paths include:

Port_Master
Port_Areas
Terminals
Terminal_Detail
Assets
Connectivity
Expansion_Projects
Port_Metrics
Sources

The Research Engine should produce data compatible with these established
contracts rather than inventing a separate AI-only schema.

---

## 22X. Governance architecture after preparation

The intended long-term flow continues beyond research preparation:

research
->
typed extraction
->
deterministic mapping
->
PORT_CORE_V2 preparation
->
ingestion bundle
->
staging
->
policy
->
human/authorized approval boundary
->
central autonomous gateway
->
canonical verification
->
provenance
->
ledger
->
replay/idempotency

The central autonomous promotion gateway is the governed integration point.

Individual agents must not bypass governance by directly calling arbitrary
per-path production RPCs.

Current Dev Agent work must stay on the safe side of these boundaries unless
the human explicitly authorizes the next write stage.

---

## 22Y. Research Engine completion roadmap

The following is the safe continuation path from the current repository
checkpoint.

### Phase 1 - current

Terminal V0.2 research extraction.

First inspect:

TrustedTerminalProfile
TRUSTED_TERMINAL_PROFILES
UntrustedResearchTerminalV2
_prepare_terminal

Then implement the smallest typed Terminal extraction + deterministic mapper
that reuses the existing trusted terminal contract.

Do not invent terminal fields.

Do not create canonical terminal IDs from LLM output.

### Phase 2 - child extraction coverage

After Terminal V0.2 is green, inspect repository gaps for remaining maritime
child/object extraction slices.

For every slice use the same discipline:

untrusted typed extraction
->
trusted registry/entity resolution
->
deterministic mapper
->
existing PORT_CORE_V2 preparation contract
->
regression tests

Do not assume the exact next child type without inspecting the repository and
roadmap state.

### Phase 3 - document understanding hardening

Complete production-quality source-content preparation:

- readable HTML extraction
- real PDF extraction
- title/publisher metadata handling
- content-type-specific safety
- deterministic source provenance preservation

Do not weaken source policy.

### Phase 4 - full read-only port research composition

Reach a state where one trusted port request can produce a complete validated
read-only PORT_CORE_V2 research bundle across the supported business paths.

No canonical writes are required to prove this phase.

### Phase 5 - pre-staging governance integration

Connect the complete read-only bundle to the existing staging preparation
contracts.

Maintain:

- source provenance
- evidence links
- identity resolution
- parent-child constraints
- target-metric guards
- idempotent natural keys
- deterministic IDs where the existing architecture requires them

### Phase 6 - controlled staging and promotion

Only after explicit human authorization:

- stage
- inspect
- apply policy
- approve
- authorize
- promote through the central gateway
- verify canonical state
- verify provenance
- verify ledger
- verify replay/idempotency

Never skip directly from LLM extraction to production write.

### Phase 7 - port scaling

Once the end-to-end pattern is proven for reference ports:

- expand trusted registry coverage
- register authoritative child identities
- onboard additional European ports
- preserve per-port official-source policy
- then expand to further regions

The goal is reusable port research architecture, not one-off scripts for every
port.

### Phase 8 - domain scaling

The final Research Engine must not remain a port-only scraper.

The same architecture should eventually support further World OS physical
domains while retaining:

- World Object identity
- evidence/provenance
- typed extraction
- deterministic validation
- authority policy
- confidence
- human/governance boundaries
- replayability

Ports are the first proving ground.

---

## 22Z. Non-negotiable Research Engine invariants

A future Dev Agent must preserve all of the following:

1. LLM output is untrusted.

2. Search provider output is untrusted.

3. Trusted identity comes from deterministic registry/resolution.

4. Trusted publisher/source authority comes from policy/registry.

5. Canonical IDs are not minted by the LLM.

6. Parent-child relationships are validated.

7. Requested metric scope is enforced.

8. Evidence is retained separately from canonical state.

9. CandidateFact preparation does not imply CandidateFact persistence.

10. Read-only ingestion bundle preparation does not imply staging approval.

11. Staging does not imply production authorization.

12. Production writes require explicit governed approval.

13. Unknown identities fail closed.

14. Unknown sources fail closed or require review according to policy.

15. Existing PORT_CORE_V2 contracts are reused before new parallel formats are
    created.

16. Existing untracked files are not disposable.

17. No git add, commit, push, migration, RPC write, or database mutation occurs
    without the active human-approved workflow.

18. The Research Engine is an evidence-to-world-state system, not an
    unrestricted web scraper.

## 22. Immediate handoff

Repository:

world-os-research-engine

Last confirmed completed slice:

Port_Area V0.2 extraction.

Last confirmed pushed commit:

a230caf Add Port Area research extraction

Next slice:

Terminal V0.2 extraction.

Exact next objective:

Inspect TrustedTerminalProfile, TRUSTED_TERMINAL_PROFILES,
UntrustedResearchTerminalV2, and _prepare_terminal, then design the smallest
Terminal V0.2 research extraction mapper that reuses existing trusted
PORT_CORE_V2 behavior.

Write permission:

NO - inspection first.
