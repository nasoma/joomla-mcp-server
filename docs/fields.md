# Article custom fields

Field definitions and groups support bounded list/detail/create/update/delete using
`fields/content/articles` and `fields/groups/content/articles`. Creation defaults unpublished.
Updates cannot change a field's name/type; trash then confirmed permanent deletion can remove
stored values. The supported creation/value-edit types are text, textarea and integer;
plugin-specific types are intentionally rejected rather than accepting unchecked configuration.

`get_article_fields` matches article attributes to field definitions. `update_article_fields`
accepts a bounded name/value map, validates names against definitions, rejects core attribute
collisions and sends Joomla's top-level field-name payload. Omitted names are not supplied.
Text values are stripped of HTML; integer values must be integers. Empty strings clear text.
An exact expected_title and optional expected_modified protect the article identity.

Definition lookup is bounded to 1000 entries; larger catalogs return an explicit error.
Enable Joomla's Fields component and applicable field plugins. Context is com_content.article;
category/user/contact fields are outside these article tools. Contracts were checked against
Joomla 4.4.13 and 5.4.0. Run `uv run pytest tests/test_fields.py` for mocked checks.
