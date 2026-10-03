# Categories and tags

Content categories and tags support list/detail/create/update/delete. All IDs are strict
positive integers; updates require exact expected_title. New resources default unpublished.
Description content uses the same content_mode policy as articles. Parent ID 1 is the
Joomla tree root. Content categories are bound to com_content, not arbitrary extensions.

Set published=-2 with confirm=true to trash a category/tag. Permanent deletion is a separate
operation requiring an already trashed resource, exact title and confirm=true. Joomla ACL,
child resources and dependency rules still govern acceptance. Article deletion stays trash-only.
Article tag assignment is explicit replacement through update_article(tags=[IDs]); tags=[] clears.

Contracts were checked against Joomla 4.4.13 and 5.4.0 content/tags Web Services plugins.
Run `uv run pytest tests/test_taxonomy.py` for mocked endpoint/payload/safety verification.
