# Native host activation (2026-10-07)

Files on disk are not activation. These observations separate discovery (the host lists the skill), selection (the model chose it without being told its name) and use (it read the pinned instructions and acted on them).

| Host | Observation | Method | Result |
| --- | --- | --- | --- |
| Codex CLI 0.160.0 | Discovery | `codex debug prompt-input` in a consumer after `apply essentials --provider both` (no inference) | Model-visible prompt lists `context-loadout`, `context-pact-hrr`, `context-review`, `context-tdd` with their descriptions, plus the AGENTS.md block |
| Codex CLI 0.160.0 | Selection and use | `codex exec` (gpt-6.1-sol, medium) in a consumer with `.agents/skills` routers but the AGENTS.md block removed; prompt asked to work "test-first" and did not name a skill | Opened `.agents/skills/context-tdd/SKILL.md`, followed it to `.context-ai/resources/procedures/tdd.md` and the pinned Matt Pocock files, wrote failing tests first, reported "Skill used: context-tdd". 68 s, 137,803 input tokens |
| Claude Code 2.1.285 | Discovery | `claude -p --setting-sources project --strict-mcp-config` in the same consumer; the `system/init` event is emitted before authentication is needed | `skills` lists `context-loadout`, `context-pact-hrr`, `context-review`, `context-tdd` |
| Claude Code (desktop session) | AGENTS.md instruction load | Reading a file inside a nested consumer from an authenticated Claude Code session in a repository without CLAUDE.md | After the read, the session surfaced the consumer's `AGENTS.md` contents, including the Context router, as additional context. Consistent with documented nested AGENTS.md loading; the exact mechanism was not separately confirmed |
| Claude Code | Selection and use | Headless `claude -p` in the consumer | **Blocked**: the standalone CLI is not logged in (`apiKeySource: none`, "Not logged in"). No credentials were borrowed. The desktop session did not load the nested consumer's `.claude/skills` (`Skill(context-tdd)` was unknown) |

To complete the Claude observation, from the consumer directory run an interactive, signed-in session and give it a test-first task without naming the skill, then check the transcript for a `Skill` call to `context-tdd`:

```sh
cd /absolute/consumer && claude
```

Headless runs need a supported sign-in or API credentials the user already authorizes; a Pro plan does not supply Agent SDK or API credit after the October 7, 2026 notice.
