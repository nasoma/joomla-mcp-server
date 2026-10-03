# Site menus and modules

Site menus and menu items support bounded list/detail/create/update/delete. Menu item lists
can filter menutype. Containers have no unpublished state; deleting one requires confirmation
and can affect navigation. Items default to drafts and must be trashed before permanent delete.
Exact expected_title is required for all existing-resource writes.

Menu-item creation supports external URL links and Joomla component links. Component links
require an explicit installed component_id from Joomla; no numeric component IDs are hardcoded.
Updates are deliberately limited to title/link/publication and preserve parent, type, menutype,
and home/default-page settings. Only HTTP(S) external links and index.php component links are
accepted. Administrator menus are not exposed.

Site modules support list/detail, custom-module creation, narrowly scoped updates and confirmed
deletion after trashing. Only mod_custom content can be edited; other module titles/positions/states
can be updated. New modules are drafts. Placement and menu assignment may require administrator
configuration; arbitrary module params, administrator modules and extension installation are not
exposed. Module content follows the common sanitized/trusted HTML policy.

Contracts were checked against Joomla 4.4.13 and 5.4.0 menus/modules plugins/controllers.
Run `uv run pytest tests/test_layout.py` for mocked verification; real acceptance requires the
corresponding Web Services plugins and Joomla ACL permissions.
