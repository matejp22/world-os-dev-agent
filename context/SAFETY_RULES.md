# SAFETY RULES

1. Read-only inspection may run autonomously if allowed by command policy.

2. Never autonomously:
- git add
- git commit
- git push
- delete files
- modify repository files
- execute database writes
- execute Supabase production writes
- run migrations
- delete database rows

3. Never read or send secrets to an AI model:
- .env
- API keys
- passwords
- tokens
- Supabase temporary project metadata
- private keys
- credentials

4. Every shell command must pass command policy before execution.

5. PowerShell output must pass through the sanitizer before being sent
to an AI reviewer.

6. Autonomous investigation loops must be bounded.

7. Production or destructive actions always require explicit human approval.
