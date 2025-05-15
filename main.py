import os
import httpx
import json
import re
from mcp.server.fastmcp import FastMCP
import markdown
import bleach

mcp = FastMCP("Joomla Articles MCP", port=8001)

JOOMLA_BASE_URL = os.getenv("JOOMLA_BASE_URL").rstrip("/")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

JOOMLA_ARTICLES_API_URL = f"{JOOMLA_BASE_URL}/api/index.php/v1/content/articles"
JOOMLA_CATEGORIES_API_URL = f"{JOOMLA_BASE_URL}/api/index.php/v1/content/categories"


def generate_alias(title: str) -> str:
    """Convert a title to a slug alias (lowercase, hyphens, no special chars)."""
    alias = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    alias = re.sub(r"\s+", "-", alias).strip("-")
    return alias


def convert_text_to_html(text: str) -> str:
    """Convert plain text to sanitized HTML using markdown and bleach."""
    html = markdown.markdown(text)

    allowed_tags = [
        "p",
        "br",
        "strong",
        "em",
        "ul",
        "ol",
        "li",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
    ]
    allowed_attributes = {}

    sanitized_html = bleach.clean(
        html, tags=allowed_tags, attributes=allowed_attributes, strip=True
    )
    return sanitized_html


@mcp.tool()
async def get_joomla_articles() -> str:
    """Retrieve all articles from the Joomla website via its API."""
    try:
        headers = {
            "Accept": "application/vnd.api+json",
            "User-Agent": "JoomlaArticlesMCP/1.0",
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(JOOMLA_ARTICLES_API_URL, headers=headers)

        if response.status_code == 200:
            return response.text
        else:
            return f"Failed to fetch articles: HTTP {response.status_code} - {response.text}"

    except httpx.HTTPError as e:
        return f"Error fetching articles: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def get_joomla_categories() -> str:
    """Retrieve all categories from the Joomla website via its API."""
    try:
        headers = {
            "Accept": "application/vnd.api+json",
            "User-Agent": "JoomlaArticlesMCP/1.0",
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(JOOMLA_CATEGORIES_API_URL, headers=headers)

        if response.status_code != 200:
            return f"Failed to fetch categories: HTTP {response.status_code} - {response.text}"

        try:
            data = json.loads(response.text)
            categories = data.get("data", [])
            if not isinstance(categories, list):
                return f"Error: Expected a list of categories, got {type(categories).__name__}: {response.text}"
            if not categories:
                return "No categories found."

            result = "Available categories:\n"
            for category in categories:
                attributes = category.get("attributes", {})
                category_id = attributes.get("id", "N/A")
                category_title = attributes.get("title", "N/A")
                result += f"- ID: {category_id}, Title: {category_title}\n"
            return result

        except json.JSONDecodeError:
            return f"Error parsing categories response: Invalid JSON - {response.text}"

    except httpx.HTTPError as e:
        return f"Error fetching categories: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def create_article(
    article_text: str,
    title: str = None,
    category_id: int = None,
    convert_plain_text: bool = True,
    published: bool = True,
) -> str:
    """
    Create a new article on the Joomla website via its API. User will provide title, content,
    category, and publication status.

    Args:
        article_text: The content of the article (plain text or HTML).
        title: Optional title (inferred from content if missing).
        category_id: Required category ID (lists categories if missing).
        convert_plain_text: Whether to auto-convert plain text to HTML (default: True).
        published: Whether the article should be published (True for state=1, False for state=0, default: True).

    Returns:
        Result string indicating success or failure.
    """
    try:
        if convert_plain_text:
            article_text = convert_text_to_html(article_text)

        if not title:
            title = (
                article_text[:50].strip() + "..."
                if len(article_text) > 50
                else article_text
            )
            title = title.replace("\n", " ").strip()

        alias = generate_alias(title)

        if category_id is None:
            categories_display = await get_joomla_categories()
            return f"{categories_display}\nPlease specify a category ID."

        if not isinstance(category_id, int):
            return "Error: Category ID must be an integer."

        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/json",
            "User-Agent": "JoomlaArticlesMCP/1.0",
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(JOOMLA_CATEGORIES_API_URL, headers=headers)

        if response.status_code != 200:
            return f"Failed to fetch categories: HTTP {response.status_code} - {response.text}"

        try:
            data = json.loads(response.text)
            categories = data.get("data", [])
            if not isinstance(categories, list) or not categories:
                return "Failed to create article: No valid categories found."
        except json.JSONDecodeError:
            return f"Failed to create article: Invalid category JSON - {response.text}"

        valid_category = any(
            category.get("attributes", {}).get("id") == category_id
            for category in categories
        )
        if not valid_category:
            return f"Error: Category ID {category_id} is not valid."

        payload = {
            "alias": alias,
            "articletext": article_text,
            "catid": category_id,
            "language": "*",
            "metadesc": "",
            "metakey": "",
            "title": title,
            "state": 1 if published else 0,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                JOOMLA_ARTICLES_API_URL, json=payload, headers=headers
            )

        if response.status_code in (200, 201):
            status = "published" if published else "unpublished"
            return f"Successfully created {status} article '{title}' in category ID {category_id}"
        else:
            return f"Failed to create article: HTTP {response.status_code} - {response.text}"

    except httpx.HTTPError as e:
        return f"Error creating article: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def manage_article_state(article_id: int, target_state: int) -> str:
    """
    Manage the state of an existing article on the Joomla website via its API. Updates the article to the
    user-specified state (published=1, unpublished=0, archived=2, trashed=-2) if it differs from the current state.

    Args:
        article_id: The ID of the existing article to check and update.
        target_state: The desired state for the article (1=published, 0=unpublished, 2=archived, -2=trashed).

    Returns:
        Result string indicating success or failure.
    """
    try:
        if not isinstance(article_id, int):
            return "Error: Article ID must be an integer."

        valid_states = {1, 0, 2, -2}
        if target_state not in valid_states:
            return f"Error: Invalid target state {target_state}. Valid states are 1 (published), 0 (unpublished), 2 (archived), -2 (trashed)."

        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/json",
            "User-Agent": "JoomlaArticlesMCP/1.0",
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{JOOMLA_ARTICLES_API_URL}/{article_id}", headers=headers
            )

        if response.status_code != 200:
            return f"Failed to fetch article: HTTP {response.status_code} - {response.text}"

        try:
            data = json.loads(response.text)
            article_data = data.get("data", {}).get("attributes", {})
            current_state = article_data.get("state", 0)
            title = article_data.get("title", "Unknown")
        except json.JSONDecodeError:
            return f"Failed to parse article data: Invalid JSON - {response.text}"

        state_map = {1: "published", 0: "unpublished", 2: "archived", -2: "trashed"}
        current_state_name = state_map.get(current_state, "unknown")
        target_state_name = state_map.get(target_state, "unknown")

        if current_state == target_state:
            return f"Article '{title}' (ID: {article_id}) is already in {current_state_name} state."

        payload = {"state": target_state}

        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{JOOMLA_ARTICLES_API_URL}/{article_id}", json=payload, headers=headers
            )

        if response.status_code in (200, 204):
            return f"Successfully updated article '{title}' (ID: {article_id}) from {current_state_name} to {target_state_name} state."
        else:
            return f"Failed to update article state: HTTP {response.status_code} - {response.text}"

    except httpx.HTTPError as e:
        return f"Error updating article state: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
async def delete_article(article_id: int) -> str:
    """
    Delete an article from the Joomla website via its API. Verifies article existence and state before deletion.

    Args:
        article_id: The ID of the article to delete.

    Returns:
        Result string indicating success or failure.
    """
    try:
        if not isinstance(article_id, int):
            return "Error: Article ID must be an integer."

        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/json",
            "User-Agent": "JoomlaArticlesMCP/1.0",
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }

        # Verify article exists and get its state
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{JOOMLA_ARTICLES_API_URL}/{article_id}", headers=headers
            )

        if response.status_code != 200:
            return (
                f"Failed to find article: HTTP {response.status_code} - {response.text}"
            )

        try:
            data = json.loads(response.text)
            article_data = data.get("data", {}).get("attributes", {})
            title = article_data.get("title", "Unknown")
            current_state = article_data.get("state", 0)
        except json.JSONDecodeError:
            return f"Failed to parse article data: Invalid JSON - {response.text}"

        # Check if article is not in trashed state (-2); move to trashed if necessary
        if current_state != -2:
            trash_result = await manage_article_state(article_id, -2)
            if "Successfully updated" not in trash_result:
                return f"Failed to move article to trashed state before deletion: {trash_result}"

        # Perform deletion
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{JOOMLA_ARTICLES_API_URL}/{article_id}", headers=headers
            )

        if response.status_code in (200, 204):
            return f"Successfully deleted article '{title}' (ID: {article_id})."
        else:
            error_detail = response.text
            return (
                f"Failed to delete article: HTTP {response.status_code} - {error_detail}. "
                "This may indicate a server-side issue or insufficient permissions. "
                "Please verify the bearer token permissions and Joomla server logs."
            )

    except httpx.HTTPError as e:
        return f"Error deleting article: {str(e)}. Please check network connectivity or Joomla API availability."
    except Exception as e:
        return f"Unexpected error: {str(e)}. Please try again or contact support."


@mcp.tool()
async def update_article(
    article_id: int,
    title: str = None,
    article_text: str = None,
    convert_plain_text: bool = True,
) -> str:
    """
    Update an existing article on the Joomla website via its API. Allows updating the title and/or body.

    Args:
        article_id: The ID of the article to update.
        title: Optional new title for the article.
        article_text: Optional new content for the article (plain text or HTML).
        convert_plain_text: Whether to auto-convert plain text to HTML (default: True).

    Returns:
        Result string indicating success or failure.
    """
    try:
        if not isinstance(article_id, int):
            return "Error: Article ID must be an integer."

        if not title and not article_text:
            return "Error: At least one of title or article_text must be provided."

        headers = {
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/json",
            "User-Agent": "JoomlaArticlesMCP/1.0",
            "Authorization": f"Bearer {BEARER_TOKEN}",
        }

        # Verify article exists
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{JOOMLA_ARTICLES_API_URL}/{article_id}", headers=headers
            )

        if response.status_code != 200:
            return (
                f"Failed to find article: HTTP {response.status_code} - {response.text}"
            )

        try:
            data = json.loads(response.text)
            article_data = data.get("data", {}).get("attributes", {})
            current_title = article_data.get("title", "Unknown")
        except json.JSONDecodeError:
            return f"Failed to parse article data: Invalid JSON - {response.text}"

        # Prepare payload with only provided fields
        payload = {}
        if title:
            payload["title"] = title
            payload["alias"] = generate_alias(title)
        if article_text:
            payload["articletext"] = (
                convert_text_to_html(article_text)
                if convert_plain_text
                else article_text
            )

        # Perform update
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{JOOMLA_ARTICLES_API_URL}/{article_id}", json=payload, headers=headers
            )

        if response.status_code in (200, 204):
            updated_fields = []
            if title:
                updated_fields.append(f"title to '{title}'")
            if article_text:
                updated_fields.append("body")
            return f"Successfully updated article '{current_title}' (ID: {article_id}) {', '.join(updated_fields)}."
        else:
            error_detail = response.text
            return (
                f"Failed to update article: HTTP {response.status_code} - {error_detail}. "
                "This may indicate a server-side issue or insufficient permissions. "
                "Please verify the bearer token permissions and Joomla server logs."
            )

    except httpx.HTTPError as e:
        return f"Error updating article: {str(e)}. Please check network connectivity or Joomla API availability."
    except Exception as e:
        return f"Unexpected error: {str(e)}. Please try again or contact support."


@mcp.prompt(name="format", description="rewrites the article title in ")
def format_title(
    title: str = None,
) -> str:
    return f"<em>{title} {title}</em>"


if __name__ == "__main__":
    mcp.run(transport="sse")
