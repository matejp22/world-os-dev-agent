# DATABASE RULES

Database:
Supabase / PostgreSQL

Default agent mode:
READ ONLY

Allowed without production approval:
- schema inspection
- safe SELECT-style investigation
- local code inspection
- dry-run reasoning

Not allowed autonomously:
- INSERT
- UPDATE
- DELETE
- DROP
- ALTER
- production RPC writes
- migration execution
- promotion to canonical production data

Staging and production writes require explicit approval according to
the relevant World OS ingestion policy.
