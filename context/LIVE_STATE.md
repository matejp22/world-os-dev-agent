# LIVE DEVELOPMENT STATE

Project:
World OS Research Engine

Repository:
C:\Users\matej\Documents\world-os-research-engine

Branch:
main

Current subsystem:
PORT_CORE_V2

Current development focus:
Research Engine port ingestion architecture and autonomous research workflows.

Latest known repository commit:
a230caf Add Port Area research extraction

Current untracked items:
- scripts/cleanup_port_core_v2_port_metrics_canary.py
- supabase/.temp/

Known status of cleanup script:
- directly related to PORT_CORE_V2 Port_Metrics canary cleanup
- dry-run by default
- contains an explicitly gated database delete path
- must NOT be executed autonomously
- currently untracked
- leave unchanged until explicit developer decision

supabase/.temp:
- local Supabase temporary/project metadata
- do not inspect contents
- do not send contents to AI
- do not delete autonomously

Completed Dev Agent capabilities:
- PowerShell execution
- stdout/stderr capture
- persistent logs
- command security policy
- blocked destructive commands
- AI planner using gpt-5.6-luna
- AI reviewer
- output sanitizer
- bounded autonomous read-only loop
- safe targeted source-code reading
- persistent project context loader

Current Dev Agent mode:
READ ONLY

Immediate next Dev Agent objective:
Improve project-state awareness so the agent can continue World OS development
from the exact current milestone instead of rediscovering the repository.

Do not autonomously change World OS Research Engine code yet.

Next architecture milestone:
Add explicit task/handoff state to AI planning, then introduce human-approved
local code patch generation.

Approval boundaries:
- repository writes require human approval
- git add requires human approval
- git commit requires human approval
- git push requires human approval
- database writes require human approval
- production changes require human approval
