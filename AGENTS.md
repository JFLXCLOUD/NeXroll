# AGENTS.md

Instructions for coding agents other than Claude Code (Codex, Gemini, Antigravity and others), for this NeXroll preroll manager fork.

[CLAUDE.md](CLAUDE.md) holds the full project instructions (stack, deploy, fork changes) and applies to every agent. Read it before making changes.

## Version control
- Work on a branch (`feature/...`, `fix/...`, `chore/...`) off `main`; never commit straight to it. Open a PR with `gh pr create` and squash-merge it.
- Push only to `origin` (`artic5693/...`). `upstream` is fetch-only: never push to it or open PRs against it.
- Stage files by name. End commits with a `Co-Authored-By:` trailer naming the agent and model that wrote the change (do not sign as Claude unless you are Claude).
- Never write secret values into any file; reference credentials by name only.

## Handoff
- Session memory shared by every agent is in the `claude-memory-shared` repo (Mac: `~/Dev/claude-memory-shared`); start at `memory/MEMORY.md`. Add durable facts there, not only in chat.
- Server-wide rules (Unraid paths, container recreation, 99:100 ownership, SSH accounts) are in the `homelab` repo's `AGENTS.md`.
