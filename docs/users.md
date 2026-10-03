# Opt-in user reads

JOOMLA_ENABLE_USERS defaults false. When true, get_joomla_users and get_joomla_user are
registered. Both are read-only; list calls are paginated. Only ID, display name, username
and block status are exposed. Email, password hashes, MFA secrets, tokens, profile params,
permissions/groups and all unknown attributes are excluded by a strict allowlist.

There are no user create/update/delete or permission-management tools. This implements the
review's proposed first-stage user capability without expanding the token's write authority.
The site must enable Web Services - Users and authorize the token's account to read users.
Do not use a Super User token merely to enable this feature.

Run `uv run pytest tests/test_users.py` for default-off, redaction and read-only checks.
