# Approved improvements — 2026-10-03

The user approved all Phase 3 items and changed the requested push target to main.
Implementation uses separate foundation, article, taxonomy, field, layout, media, user,
verification and packaging commits. No live-site operations are used during verification.

| Review items | Implementation | Checks and documentation |
| --- | --- | --- |
| A1 | Validated Settings with secret token, URL/HTTPS and bounded configuration | test_foundation, test_edge_cases; architecture/README |
| A2 | Independent PATCH intro/full text, explicit empty values, alias preservation | test_articles; articles.md |
| A3 | Bounded lists, filters, article detail, category detail validation | test_articles; articles.md |
| A4 | Normalized JSON:API resource IDs and validated null/shape/paging responses | test_foundation/test_edge_cases; architecture.md |
| A5 | Safe bounded ToolErrors and real MCP error results | test_foundation/test_compatibility/test_tool_contracts; README |
| A6 | Sanitized Markdown/HTML plus explicit opt-in trusted HTML | test_articles; articles.md |
| A7 | Read-only mode, exact identity checks, confirmation, state guards and annotations | test_articles/test_taxonomy/test_tool_contracts; README |
| A8 | Pytest/asyncio/MockTransport, all-tool failure guards, source-contract version settings, CI | tests; testing.md |
| A9 | Strict positive IDs, bounded values, nullable optional arguments and valid states | test_articles/test_fields/test_edge_cases; README |
| A10 | Source-text title inference, Joomla alias generation, returned created IDs | test_articles; articles.md |
| A11 | Shared lifespan client, configurable timeout, bounded GET retries/Retry-After, no write retries | test_foundation/test_edge_cases; architecture.md |
| A12 | Separate config/client/models/content/tool modules and safe stderr operation logs | unit and stdio tests; architecture.md |
| A13 | Correct inventory, env example, least-privilege setup, validated Smithery schema | README, .env.example, smithery.yaml, testing.md |
| A14 | Installable console command, dev dependencies, non-root/pinned Docker, ignore rules and build CI | uv build, stdio smoke, CI |
| F1 | Category/tag CRUD and article tag replacement | test_taxonomy/test_edge_cases; taxonomy.md |
| F2 | Field definitions/groups CRUD and article field values | test_fields; fields.md |
| F3 | Image upload/list/detail plus article image metadata | test_media; media.md |
| F4 | Site menus/items CRUD and scoped site module management | test_layout; layout.md |
| F5 | Default-off user reads, sensitive-attribute allowlist, no user writes | test_users; users.md |

The approved feature scope starts with safe common Joomla 4/5 contracts: text/textarea/integer
field writes, mod_custom content writes, site layouts, local-images adapter uploads and read-only
users. Arbitrary plugin-specific payloads, administrator layouts, media overwrite/delete and
user/permission writes remain outside those contracts. New content defaults to drafts.

Breaking changes are documented in README: Python 3.14+, MCP SDK 2, structured results,
paginated lists, required exact-title identity checks, draft defaults and sanitized HTML defaults.
Real Joomla integration is not claimed by mocked tests. Media requires Joomla 4.1+.
