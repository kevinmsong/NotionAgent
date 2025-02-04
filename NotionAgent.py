import streamlit as st
import re
import logging
from typing import List, Dict, Set, Optional, Callable

import google.generativeai as genai
from notion_client import Client
from notion_client.errors import APIResponseError

# ------------------------------------------------------------------------------
# Configure Logging and API Keys
# ------------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Use st.secrets or environment variables in production.
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "your-notion-api-key")
# Use your Gemini API key from secrets; a default is provided if not set.
GEMINI_API_KEY = st.secrets.get("gemini_api_key", "AIzaSyBafl-5GBLPsxHpsofFaDE03aMVCqh-wTU")

# Initialize the Notion client and configure Gemini.
notion = Client(auth=NOTION_API_KEY)
genai.configure(api_key=GEMINI_API_KEY)

# ------------------------------------------------------------------------------
# Helper Functions for Notion Parsing and Recursion
# ------------------------------------------------------------------------------

def extract_page_id(url: str) -> str:
    """
    Extracts the 32-digit page ID from a Notion URL and formats it as a UUID.
    """
    patterns = [
        r'notion\.so/[^/]+/[^-]+-([a-f0-9]{32})',  # Workspace/page-name format
        r'([a-f0-9]{32})',                        # Direct ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            page_id = match.group(1)
            return f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
    raise ValueError("Could not extract page ID from URL.")

def safe_get_text(content: Dict, field: str) -> str:
    """
    Safely extracts text from a content field handling different data structures.
    """
    try:
        text_array = content.get(field, [])
        if isinstance(text_array, list):
            return " ".join(
                text.get("plain_text", "") if isinstance(text, dict) else str(text)
                for text in text_array
            )
        elif isinstance(text_array, dict):
            return text_array.get("plain_text", "")
        elif isinstance(text_array, str):
            return text_array
        return ""
    except Exception as e:
        logger.debug(f"Error extracting text from {field}: {str(e)}")
        return ""

def get_block_text(block: Dict) -> str:
    """
    Extracts text content from a block's available text fields.
    """
    if not block or "type" not in block:
        return ""
    block_type = block["type"]
    block_content = block.get(block_type, {})
    for field in ["text", "rich_text", "title", "content"]:
        text = safe_get_text(block_content, field)
        if text:
            return text
    if block_type == "child_page":
        return block_content.get("title", "")
    return ""

def process_block(block: Dict) -> str:
    """
    Processes a block and returns its formatted content based on its type.
    """
    if not block or "type" not in block:
        return ""
    block_type = block["type"]
    text = get_block_text(block)
    if not text.strip():
        return ""

    if block_type == "heading_1":
        return f"\n# {text}\n"
    elif block_type == "heading_2":
        return f"\n## {text}\n"
    elif block_type == "heading_3":
        return f"\n### {text}\n"
    elif block_type in ["bulleted_list_item", "numbered_list_item"]:
        return f"• {text}"
    elif block_type == "paragraph":
        return text
    elif block_type == "toggle":
        return f"▶ {text}"
    elif block_type == "to_do":
        checked = block.get(block_type, {}).get("checked", False)
        return f"{'[x]' if checked else '[ ]'} {text}"
    elif block_type == "code":
        language = block.get(block_type, {}).get("language", "")
        return f"\n```{language}\n{text}\n```\n"
    elif block_type == "quote":
        return f"> {text}"
    elif block_type == "callout":
        emoji = block.get(block_type, {}).get("icon", {}).get("emoji", "")
        return f"{emoji} {text}"
    return text

def fetch_database_entries(
    database_id: str, 
    visited: Optional[Set[str]] = None, 
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[str]:
    """
    Recursively fetches entries from a child database and indexes each page.
    Each new page (database entry) increments the progress counter.
    """
    if visited is None:
        visited = set()
    if database_id in visited:
        return []
    visited.add(database_id)
    content = []
    try:
        cursor = None
        while True:
            response = notion.databases.query(database_id=database_id, start_cursor=cursor, page_size=100)
            entries = response.get("results", [])
            for entry in entries:
                page_title = ""
                for prop in entry.get("properties", {}).values():
                    if prop.get("type") == "title":
                        page_title = safe_get_text(prop, "title")
                        break
                if not page_title:
                    page_title = "Untitled"
                content.append(f"\n#### {page_title}\n")
                if progress_callback:
                    progress_callback(1)
                entry_id = entry.get("id")
                entry_blocks = fetch_block_children(entry_id, visited=visited, progress_callback=progress_callback)
                if entry_blocks:
                    content.extend(entry_blocks)
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
    except Exception as e:
        logger.error(f"Error fetching database entries: {str(e)}")
    return content

def fetch_block_children(
    block_id: str, 
    indent: int = 0, 
    visited: Optional[Set[str]] = None,
    progress_callback: Optional[Callable[[int], None]] = None
) -> List[str]:
    """
    Recursively fetches and formats the block content of a Notion page,
    handling nested pages and embedded databases.
    """
    if visited is None:
        visited = set()
    if block_id in visited:
        return []
    visited.add(block_id)

    content = []
    try:
        cursor = None
        current_group = []

        while True:
            response = notion.blocks.children.list(
                block_id=block_id,
                start_cursor=cursor,
                page_size=100
            )
            blocks = response.get("results", [])
            for b in blocks:
                block_type = b.get("type", "")
                
                # Handle child pages:
                if block_type == "child_page":
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    page_title = b.get("child_page", {}).get("title", "Untitled")
                    content.append(f"\n### {page_title}\n")
                    if progress_callback:
                        progress_callback(1)
                    child_page_id = b.get("id")
                    child_content = fetch_block_children(child_page_id, indent + 1, visited, progress_callback)
                    if child_content:
                        content.extend(child_content)
                    continue

                # Handle child databases:
                if block_type == "child_database":
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    db_title = b.get("child_database", {}).get("title", "Database")
                    content.append(f"\n### Database: {db_title}\n")
                    database_id = b.get("id")
                    db_entries = fetch_database_entries(database_id, visited, progress_callback)
                    if db_entries:
                        content.extend(db_entries)
                    continue

                # Process regular blocks:
                block_content = process_block(b)
                if not block_content:
                    continue

                # If it's a heading block, flush current group first:
                if block_type.startswith("heading_"):
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    content.append(block_content)
                elif block_type in ["bulleted_list_item", "numbered_list_item", "paragraph"]:
                    current_group.append(block_content)
                else:
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    content.append(block_content)

                # Check for nested children in the same block:
                if b.get("has_children", False):
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    child_content = fetch_block_children(b["id"], indent + 1, visited, progress_callback)
                    if child_content:
                        content.extend(child_content)

            # After processing blocks in this batch, flush if needed:
            if current_group:
                content.append(" ".join(current_group))
                current_group = []

            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")

    except APIResponseError as e:
        logger.error(f"Error fetching blocks for id {block_id}: {str(e)}")

    return content

# ------------------------------------------------------------------------------
# Query Function Using Gemini 2.0 Flash AI
# ------------------------------------------------------------------------------
def query_gemini(content: str, question: str) -> str:
    """
    Sends the indexed Notion content and a question to Gemini 2.0 Flash AI.
    No memory or context is stored between queries.
    """
    prompt = (
        "Below is the recursively indexed content of a Notion page (including subpages and database entries). "
        "Analyze the content and answer the question that follows.\n\n"
        f"{content}\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )
    try:
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        response = model.generate_content(prompt)
        return response.text.strip() if hasattr(response, "text") else response
    except Exception as e:
        logger.error(f"Error querying Gemini: {str(e)}")
        return f"Error querying Gemini: {str(e)}"

# ------------------------------------------------------------------------------
# Function to Fetch Notion Content (Always Fresh; No Caching)
# ------------------------------------------------------------------------------
def fetch_notion_content(notion_url: str, progress_callback: Optional[Callable[[int], None]] = None) -> str:
    """
    Fetch content from a Notion URL by recursively walking the page.
    This function is called every time a question is asked, ensuring no memory is kept.
    """
    page_id = extract_page_id(notion_url)
    try:
        page = notion.pages.retrieve(page_id)
        title = ""
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = safe_get_text(prop, "title")
                break
        st.info(f"Accessed page: {title or 'Untitled'}")
    except APIResponseError as e:
        st.warning(
            "Could not retrieve page properties. The integration might not have full access to metadata, "
            "but block-level content will still be indexed."
        )
        logger.warning(f"Page retrieve error: {str(e)}")

    st.spinner("Fetching content from Notion...")
    content_blocks = fetch_block_children(page_id, visited=set(), progress_callback=progress_callback)
    if not content_blocks:
        return ""
    return "\n\n".join(content_blocks)

# ------------------------------------------------------------------------------
# Streamlit UI
# ------------------------------------------------------------------------------
def main():
    st.title("Notion Page QA (Memoryless) with Gemini 2.0 Flash")
    st.markdown(
        """
        This app lets you enter a Notion page URL (with proper integration) and ask questions
        about its content. The page is fully indexed each time you ask a question—absolutely no caching 
        or memory from previous runs. The answer is generated using Gemini 2.0 Flash AI.
        """
    )

    notion_url = st.text_input("Enter Notion Page URL", placeholder="https://www.notion.so/your-page-url")

    # Simple progress counter for demonstration
    progress_state = {"count": 0}
    progress_placeholder = st.empty()

    def progress_callback(n: int):
        progress_state["count"] += n
        progress_placeholder.text(f"Indexed pages: {progress_state['count']}")

    question = st.text_input("Ask a question about the above Notion page", 
                             placeholder="e.g., What is the main objective?")

    if st.button("Get Answer") and notion_url.strip() and question.strip():
        # We fetch the content from scratch every time
        with st.spinner("Indexing Notion page (memoryless fetch)..."):
            progress_state["count"] = 0
            notion_content = fetch_notion_content(notion_url, progress_callback=progress_callback)

        if not notion_content:
            st.error("No content found in the page.")
        else:
            st.success("Content indexed successfully!")
            with st.expander("Show Indexed Content (optional debugging)"):
                st.text_area("Indexed Content", notion_content, height=300)
            with st.spinner("Querying Gemini 2.0 Flash (memoryless AI)..."):
                answer = query_gemini(notion_content, question)
            st.markdown("**Answer:**")
            st.write(answer)

if __name__ == "__main__":
    main()
