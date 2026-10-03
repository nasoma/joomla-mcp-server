# Joomla MCP Server

A Python stdio MCP server for Joomla 4/5 Web Services, using MCP SDK 2's `MCPServer`
(the successor to `FastMCP`). Manage articles, categories, tags, custom fields, media,
site menus and site modules. User reads are separately enabled and exclude sensitive data.

## Requirements and installation

- Python 3.14+; `.python-version` and Docker select 3.14.8.
- [uv](https://docs.astral.sh/uv/) (Docker pins 0.12.22).
- Joomla 4 or 5 with the appropriate Web Services plugins; media needs Joomla 4.1+.
- A dedicated API account authorized for the operations you intend to use.

```sh
git clone https://github.com/nasoma/joomla-mcp-server.git
cd joomla-mcp-server
uv sync --locked
cp .env.example .env
```

Edit `.env` locally with your site URL and token. `.env` and `.env.*` are ignored;
`.env.example` contains placeholders only. The server itself reads the process environment,
not `.env` files. To explicitly load your local file:

```sh
uv run --locked --env-file .env joomla-mcp
```

`uv run --locked main.py` remains available with variables supplied by your MCP client.
The package also builds an installable `joomla-mcp` console command.
Missing/invalid configuration produces a concise stderr error and exit code 2.

### Joomla account and plugins

Enable **API Authentication - Web Services Joomla Token** and **User - Joomla API Token**.
Enable the relevant **Web Services - Content, Tags, Media, Menus, Modules or Users** plugins.
Enable the Fields component/plugins when using article custom fields.

Use a dedicated account with `core.login.api` and only the Joomla ACL permissions needed
for your workflows. Generate/copy its API token from the user profile's Joomla API Token tab;
UI details vary by Joomla version. Avoid a Super User token for routine content tasks.
Do not put the real token in committed files, examples, shell commands, or logs.

### MCP client configuration

Adapt the following to your client's configuration format, replacing placeholders locally:

```json
{
  "mcpServers": {
    "Joomla Articles MCP": {
      "command": "/absolute/path/to/uv",
      "args": ["--directory", "/absolute/path/to/joomla-mcp-server", "run", "--locked", "joomla-mcp"],
      "env": {
        "JOOMLA_BASE_URL": "https://example.com",
        "BEARER_TOKEN": "<supply-token-securely>",
        "JOOMLA_READ_ONLY": "true"
      }
    }
  }
}
```

For local development, HTTP is permitted only for localhost/127.0.0.1/::1 with
`JOOMLA_ALLOW_LOCAL_HTTP=true`. Supply the Joomla site root, not `/api/index.php/v1`.
No HTTP port is exposed; keep stdin open for stdio clients.

## Tools

| Area | Tools |
| --- | --- |
| Articles | `get_joomla_articles`, `get_joomla_article`, `create_article`, `update_article`, `manage_article_state`, `move_article_to_trash` |
| Categories | `get_joomla_categories`, `get_joomla_category`, `create_category`, `update_category`, `delete_category` |
| Tags | `get_joomla_tags`, `get_joomla_tag`, `create_tag`, `update_tag`, `delete_tag`; article tag assignment through `update_article(tags=[IDs])` |
| Fields | `get_joomla_fields`, `get_joomla_field`, `create_field`, `update_field`, `delete_field`, `get_joomla_field_groups`, `get_joomla_field_group`, `create_field_group`, `update_field_group`, `delete_field_group`, `get_article_fields`, `update_article_fields` |
| Media | `get_joomla_media`, `get_joomla_media_file`, `upload_media`, `update_article_images` |
| Site menus | `get_joomla_menus`, `get_joomla_menu`, `create_menu`, `update_menu`, `delete_menu`, `get_joomla_menu_items`, `get_joomla_menu_item`, `create_menu_item`, `update_menu_item`, `delete_menu_item` |
| Site modules | `get_joomla_modules`, `get_joomla_module`, `create_custom_module`, `update_module`, `delete_module` |
| Users (opt-in) | `get_joomla_users`, `get_joomla_user`; read-only |

Tool input schemas contain types, bounds and descriptions. IDs must be positive integers;
booleans and numeric strings are rejected. Lists default to 20 rows and allow at most 100.
For articles, use search/category_id/state/tag_id filters and follow `pagination.next_offset`.
Article list content is omitted by default; request `include_content=true` or detail lookup.
Media directories are byte-bounded and sliced locally because Joomla does not paginate them.

Success results are structured objects with `ok: true`, normalized `data`, and optional
`pagination`, `updated_fields` or `changed`. Resource IDs in results are strings; supply IDs
as integers when calling a tool. Errors are MCP tool errors (`is_error=true`), with safe,
bounded messages. API bodies, credentials and raw network exceptions are not returned.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `JOOMLA_BASE_URL`, `BEARER_TOKEN` | Required | HTTPS site root and secret token |
| `JOOMLA_VERSION` | `5` | Supported major version, `4` or `5`; tools use their common API contract |
| `JOOMLA_READ_ONLY` | `false` | Reject mutations |
| `JOOMLA_ALLOW_TRUSTED_HTML` | `false` | Permit explicitly selected trusted HTML |
| `JOOMLA_ENABLE_USERS` | `false` | Register filtered user read tools |
| `JOOMLA_ALLOW_LOCAL_HTTP` | `false` | Loopback development exception |
| `JOOMLA_TIMEOUT` | `20` | Per-request timeout, seconds (maximum 120) |
| `JOOMLA_READ_RETRIES` | `2` | Extra safe-read attempts (0–3); writes never retry |
| `JOOMLA_MAX_RESPONSE_BYTES` | `2000000` | Maximum decoded API response bytes |
| `JOOMLA_MAX_UPLOAD_BYTES` | `5000000` | Maximum decoded image upload bytes |

Boolean values accept true/false or 1/0. Redirects and proxy environment lookup are disabled.
Read Retry-After values over five seconds return a failure so the caller can reschedule.

## License

MIT; see [LICENSE](LICENSE).
