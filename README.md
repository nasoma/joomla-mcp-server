# Joomla MCP Server

Connect an AI assistant to your existing Joomla 4 or 5 website so it can read and manage
articles, categories, tags and other supported site content.

You configure **two places**: your Joomla website and the computer running your AI assistant.
This Python server runs on your computer and calls Joomla's built-in Web Services API over
HTTPS. You do not install this repository as a Joomla extension or upload it to your web host.
Your AI app must support **local MCP servers using stdio**; the example below uses Claude Desktop.

## Set up your Joomla website

### 1. Enable the required plugins

Sign in to your Joomla Administrator as a Super User. Open **System → Manage → Plugins**
(or **System → Plugins**, depending on your administrator layout). Search for and enable:

| Plugin | Needed for |
| --- | --- |
| **API Authentication - Web Services Joomla Token** | Authenticating API requests with your token |
| **User - Joomla API Token** | Creating and managing a user's API token |
| **Web Services - Content** | Articles, content categories and article fields |

Start with these three. If you want additional tools, also enable the corresponding
**Web Services - Tags**, **Media**, **Menus**, **Modules** or **Users** plugin. Media tools
require Joomla 4.1 or later. Custom fields also need Joomla's Fields component and field plugins.

### 2. Choose the Joomla account the assistant will use

The API token belongs to a Joomla user. Requests have that user's permissions.
Use a dedicated account for this connection, rather than your everyday Super User account.

For a dedicated account:

1. Open **Users → Groups → New** and create a group such as `MCP Content Editors`.
   For a restricted starting point, select **Registered** as the parent group.
2. Open **System → Global Configuration → Permissions**, select your group, and allow
   **Web Services Login** (`core.login.api`). Also allow **Administrator Login** so this
   account can open its own profile and copy its token. Check that the calculated permissions
   show Allowed; leave Super User access unset.
3. For article management, open **Content → Articles → Options → Permissions**. Give the
   group **Access Administration Interface** for the Articles component, then only the
   actions it needs: **Create** for new articles, **Edit** for updates, and
   **Edit State** for publishing, unpublishing and trashing. Category permissions can restrict
   these operations further. Configure other components' permissions only if you use their tools.
4. Open **Users → Manage → New**, create the dedicated account and assign it to that group.
   Ensure the account is enabled, activated and not blocked.
5. Return to **System → Plugins**, open **User - Joomla API Token**, and add this user's
   group to **Allowed User Groups**, then save. The default commonly allows only Super Users;
   a newly created account may otherwise have no token tab. Do not clear the group restriction
   just to make every account eligible.

An explicit Denied permission inherited from another group/category cannot be fixed by
allowing it in a child group. Ask your Joomla administrator to check the calculated permissions
if access is still denied. Creating an API token does not grant additional permissions.

### 3. Copy that account's API token

Sign in to Joomla **as the account whose token you will use**. Open your own profile
using the user menu in the top-right of Administrator (**Edit Account** or **Profile**,
depending on the version), and select
**Joomla API Token**.

- If Joomla says the account has no token yet, save the profile, then reopen it.
- Set **Active** to **Yes** if that control is shown, and save.
- Copy the value in **Token**. This is what you will put in `BEARER_TOKEN` below.
- **Reset → Yes**, followed by saving, replaces the token and invalidates the old one.

You can only view your own token. Editing another user's account as a Super User does not
let you copy their token. If the tab is missing, check the token plugin and its allowed groups.
See Joomla's [token plugin settings](https://github.com/joomla/joomla-cms/blob/5.4.0/plugins/user/token/token.xml)
and [profile controls](https://github.com/joomla/joomla-cms/blob/5.4.0/plugins/user/token/forms/token.xml).

## Set up the server on your computer

### 4. Install Git and uv, then download this repository

Use the computer on which your MCP-compatible AI app runs. Install
[Git](https://git-scm.com/downloads) if `git --version` does not work.

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), which will manage Python
and this server's dependencies. On macOS/Linux:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows, use PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Reopen your terminal after installation, then run these commands on either platform:

```sh
uv --version
git clone https://github.com/nasoma/joomla-mcp-server.git
cd joomla-mcp-server
uv python install 3.14.8
uv sync --locked
```

If you already cloned this repository, open that folder instead of cloning again.
`uv sync` creates the local `.venv` and installs the server. You do not need to activate it.

### 5. Put your website URL and token in a local .env file

In the repository folder, copy `.env.example` to `.env`.

macOS/Linux:

```sh
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Open `.env` in a text editor and replace these values:

```dotenv
JOOMLA_BASE_URL=https://your-joomla-site.com
BEARER_TOKEN=paste-your-own-joomla-api-token-here
JOOMLA_VERSION=5
JOOMLA_READ_ONLY=true
```

Set `JOOMLA_VERSION=4` if your site uses Joomla 4. Leave the other example settings unchanged
for the initial connection. Setting `JOOMLA_READ_ONLY=true` lets you first confirm access
without allowing the assistant to change your website.

Use your site's public HTTPS URL. If Joomla is in a subfolder, include it, for example
`https://example.com/joomla`. Do not append `/administrator` or `/api/index.php/v1`.
The server adds the API path itself. Your host/firewall must permit access to that API.

Keep `.env` private. It is ignored by Git; do not share it or replace placeholders in this README
with a real token. On macOS/Linux, you can restrict access with `chmod 600 .env`.
The server reads environment variables; `uv` loads this file only when you pass `--env-file`.

### 6. Confirm the server can start

From the repository folder, run:

```sh
uv run --locked --env-file .env joomla-mcp
```

A running server normally waits quietly for an MCP client. It does not open a browser,
print an article list or start a web page. Press **Ctrl+C** to stop this manual run.
Starting successfully checks local configuration; the first tool request in step 7 checks
access to your Joomla website.

## Connect your AI assistant

### 7. Add the server to Claude Desktop

Install and open **Claude Desktop** on your computer. These settings go in its local
configuration file, not in a chat message or the Claude website's connector URL field.
Claude Desktop starts the server for you; you do not need to keep step 6 running.

First, open a terminal **inside the cloned `joomla-mcp-server` folder** and find the two paths:

| Placeholder in the JSON below | macOS/Linux command | Windows PowerShell command |
| --- | --- | --- |
| `{{PATH_TO_UV}}` | `which uv` | `(Get-Command uv).Source` |
| `{{PATH_TO_PROJECT}}` | `pwd` | `(Get-Location).Path` |

Copy each command's output. For example, `which uv` might return
`/Users/you/.local/bin/uv`, and `pwd` might return `/Users/you/joomla-mcp-server`.
Use your own output, including the complete path. Do not use `~` or leave placeholders unchanged.

Open the configuration file:

1. On macOS, choose **Claude → Settings…** from the menu bar. On Windows, open
   **Settings** in the Claude Desktop app.
2. Select **Developer → Edit Config**. This opens `claude_desktop_config.json`.
3. If the file is empty, paste the complete JSON below. If it already contains
   `mcpServers`, add the **Joomla Articles MCP** entry inside that object and keep
   your existing servers.

The file lives here if you need to open it manually:

| System | Configuration file |
| --- | --- |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

On macOS, use Finder **Go → Go to Folder…** to open `~/Library/Application Support/Claude`.
On Windows, press **Win+R**, enter `%APPDATA%\Claude`, and open the file there.
See the official [Claude Desktop local MCP guide](https://modelcontextprotocol.io/docs/develop/connect-local-servers).

```json
{
  "mcpServers": {
    "Joomla Articles MCP": {
      "command": "{{PATH_TO_UV}}",
      "args": [
        "--directory",
        "{{PATH_TO_PROJECT}}",
        "run",
        "--locked",
        "--env-file",
        "{{PATH_TO_PROJECT}}/.env",
        "joomla-mcp"
      ]
    }
  }
}
```

Replace `{{PATH_TO_UV}}` with the `uv` path and replace **both** occurrences of
`{{PATH_TO_PROJECT}}` with the repository path. Keep `/.env` on the second occurrence;
it points to the file you created in step 5. The JSON must contain no comments.

On Windows, use the full `uv.exe` path. Use forward slashes, such as
`C:/Users/you/joomla-mcp-server`, or double each backslash in JSON, such as
`C:\\Users\\you\\joomla-mcp-server`. No token needs to be copied into this JSON;
`uv` loads it from your local `.env` file.

Save the file, **fully quit Claude Desktop**, then reopen it. In a conversation, open
**Add files, connectors, and more → Connectors → Manage connectors** and check that
**Joomla Articles MCP** is available. Then ask:

> Use get_joomla_articles to list the first five articles on my Joomla website. Do not change anything.

Approve the read request if Claude asks. A successful response contains article IDs/titles,
or an empty list if the account can see no articles. An empty list is different from an API error.

For another MCP app, put the same command and arguments in its **local/stdio server**
configuration. This server does not provide an HTTP MCP URL for a remote connector.

### 8. Enable content changes when you are ready

After the read request succeeds, change this line in `.env`:

```dotenv
JOOMLA_READ_ONLY=false
```

Restart your AI app so it reloads the configuration. The account's Joomla permissions still
control which changes are possible. New articles default to unpublished drafts. Updates need
the exact existing title; trash operations also need explicit confirmation. For example:

> Show my content categories, then create an unpublished draft called “MCP setup check” in the category I choose.

Optional features can be enabled later: use `JOOMLA_ENABLE_USERS=true` for filtered user reads,
and enable the matching Joomla Web Services plugins for other tool families.

### Choosing an article category

`create_article` and `update_article` accept either `category_id` or `category_name`.
For example, “Move article 87 to Blog” can use `category_name="Blog"`; the server resolves
an exact, case-insensitive match to the category ID. It checks all available category pages
(up to 1,000 categories), so a match on the first page cannot hide a duplicate on a later page.

If no category is supplied when creating an article, no exact name matches, or several
categories share the name, the server makes no change and tells your assistant to ask
which category ID to use. Ambiguous results include candidate IDs and parent IDs.
Supplying both a name and ID requires them to agree. These clarification messages are
shown through your assistant's chat; the server does not open a client-specific popup.

Publishing an existing article keeps its current category. To publish in another category,
ask the assistant to move it first, then publish it after the move succeeds.

## Setup troubleshooting

| What you see | What to check |
| --- | --- |
| No Joomla API Token tab or a blank token | Enable User - Joomla API Token, include the account's group in Allowed User Groups, sign in as that account, save and reopen its profile. |
| HTTP 401 | Check API Authentication - Web Services Joomla Token, the copied token and its Active setting. If the token was reset, update `.env` and restart the client. |
| HTTP 403 | Check the account's Web Services Login permission, group eligibility and the component/category permissions for the requested operation. |
| HTTP 500 | The tool includes Joomla JSON error titles/details when available, with credentials and paths redacted. Read the article before retrying a failed write because it may already have saved. If Joomla only reports an internal server error, ask your host for the matching PHP error-log entry; local MCP stderr only shows the HTTP status. |
| HTTP 404 | Check the site root/subfolder URL and the matching Web Services plugin. The host must route `/api/index.php/v1/...` to Joomla rather than block it. |
| Network failure or timeout | Check that your computer can reach the site's HTTPS URL and that the host/firewall permits API requests. |
| Invalid Joomla response / expected JSON | A login page, hosting error or firewall challenge may have been returned instead of API JSON. Check the API route with your host. |
| Configuration error about URL/token | Confirm `.env` contains both values and the client command includes the correct absolute `--env-file` path. |
| Server missing from your AI app | Check JSON syntax, absolute paths and `uv --version`; fully restart the app and inspect its MCP error logs. |
| Server waits silently in the terminal | This is expected for stdio; connect your AI app as described in step 7. |
| Writes are disabled | Change JOOMLA_READ_ONLY to false in `.env`, then restart the app. |

Joomla's [Web Services guide](https://manual.joomla.org/docs/5.4/general-concepts/webservices/)
explains the API and account prerequisites. Never post your token when asking for setup help.

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
