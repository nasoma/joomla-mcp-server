# Media and article images

Media tools use the built-in `local-images:/` adapter. Paths accept simple alphanumeric,
underscore, hyphen and dot segments; absolute filesystem paths, traversal, encoded paths,
hidden segments and arbitrary providers are rejected. These tools do not read local files.
Uploads accept base64 content directly, not a local filename or remote URL.

PNG, JPEG, GIF and WebP uploads must be valid images, with matching MIME/extension, below
JOOMLA_MAX_UPLOAD_BYTES (default 5 MB) and 25 million pixels. Pillow verifies image structure.
SVG and executable content are excluded. Uploads always send override=false and are never
retried automatically. Joomla may reject uploads for stricter media settings or ACL rules.
No media overwrite, rename or delete tool is exposed.

Joomla 4.1+ media APIs return path resources with id=0 and do not support ordinary list
pagination. Directory responses remain byte-bounded; get_joomla_media slices results locally
and reports server_paginated=false. Narrow the directory/search if the response exceeds
JOOMLA_MAX_RESPONSE_BYTES. Results exclude base64 content and temporary URLs.

update_article_images edits only specified image, alt and caption properties; it retains other
image metadata. References must be HTTPS URLs or safe relative images/ paths; empty strings
clear fields. Exact article title and optional modified timestamp are checked before PATCH.

Contracts were checked against Joomla 4.4.13 and 5.4.0 media plugins/controllers/models/views.
Run `uv run pytest tests/test_media.py` for mocked checks. Joomla 4.0 lacks the media API.
