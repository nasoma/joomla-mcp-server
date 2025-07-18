# Joomla MCP Server

[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/nasoma-joomla-mcp-server-badge.png)](https://mseep.ai/app/nasoma-joomla-mcp-server)
[![smithery badge](https://smithery.ai/badge/@nasoma/joomla-mcp-server)](https://smithery.ai/server/@nasoma/joomla-mcp-server)

## Table of Contents
- [Introduction](#introduction)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Available Tools](#available-tools)
- [Security Considerations](#security-considerations)

## Introduction
The Joomla MCP (Model Context Protocol) Server enables AI assistants, such as Claude, to interact with Joomla websites via the Joomla Web Services API. It provides tools to manage articles using an AI assistant.

## Features
- Retrieve all articles from a Joomla website
- List all content categories
- Create new articles
- Manage article states (published, unpublished, trashed, or archived)
- Delete articles
- Update articles (requires both introtext and fulltext, with a "Read more" break)

## Requirements
- Python 3.11+
- Joomla 4.x or 5.x with the Web Services API plugin enabled
- API Bearer token for authentication


## Installation


### Create a Joomla API Token

1. Access User Profile: Log in to the Joomla Administrator interface and navigate to the Users menu, then select Manage.

2. Edit Super User: Find and click on the Super User account (or the desired user) to edit their profile.

3. Generate Token: Go to the Joomla API Token tab, click the Generate button, and copy the displayed token.


###  Install the Project/Server locally
1. Clone the repository:
```

git clone https://github.com/nasoma/joomla-mcp-server.git
cd joomla-mcp-server

```
2. Set up a virtual environment and install dependencies using `uv` (a Python dependency manager, see [uv documentation](https://github.com/astral-sh/uv)). If uv is installed run:

```
uv sync 
```


### Installing on Claude or other AI assistants
#### Claude Desktop

Add this to your `claude_desktop_config.json`:


```json
{
  "mcpServers": {
    "Joomla Articles MCP": {
      "command": "{{PATH_TO_UV}}",
      "args": [
        "--directory",
        "{{PATH_TO_PROJECT}}",
        "run",
        "main.py"
      ],
      "env": {
        "JOOMLA_BASE_URL": "<your_joomla_website_url>",
        "BEARER_TOKEN": "<your_joomla_api_token>"
      }
    }
  }
}


```
Replace `{{PATH_TO_UV}}` with the path to `uv` (run `which uv` to find it) and `{{PATH_TO_PROJECT}}` with the project directory path (run `pwd` in the repository root).




## Available Tools

### 1. get_joomla_articles()
Retrieves all articles from the Joomla website via its API.



### 2. get_joomla_categories()
Retrieves all categories from the Joomla website and formats them in a readable list.


### 3. create_article()
Creates a new article on the Joomla website via its API.

**Parameters:**
- `article_text` (required): The content of the article (plain text or HTML)
- `title` (optional): The article title (inferred from content if not provided)
- `category_id` (optional): The category ID for the article
- `convert_plain_text` (optional, default: True): Auto-converts plain text to HTML
- `published` (optional, default: True): Publishes the article immediately

### 4. manage_article_state()
Manages the state of an existing article on the Joomla website via its API.

**Parameters:**
- `article_id` (required): The ID of the existing article to check and update
- `target_state` (required): The desired state for the article (1=published, 0=unpublished, 2=archived, -2=trashed)

### 5. delete_article()
Deletes an article from the Joomla website via its API.

**Parameters:**
- `article_id` (required): The ID of the article to delete

### 6. update_article()
Updates an existing article on the Joomla website via its API. Both `introtext` and `fulltext` are required to align with Joomla’s article structure (introtext for the teaser, fulltext for the content after a "Read more" break).

**Parameters:**
- `article_id` (required): The ID of the article to update
- `title` (optional): New title for the article
- `introtext` (required): Introductory text for the article (plain text or HTML)
- `fulltext` (required): Full content for the article (plain text or HTML)
- `metadesc` (optional): Meta description for the article





## Security Considerations

- The Joomla API Token has access to your site. Treat it the same way you treat your passwords.
- The server sanitizes HTML content to prevent XSS attacks
- Ensure your Joomla website uses HTTPS to secure API communications.

## License
This project is licensed under the MIT License. 