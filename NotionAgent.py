import streamlit as st
import re
import logging
from typing import List, Dict, Set, Optional, Callable

import openai
from notion_client import Client
from notion_client.errors import APIResponseError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# Configure API keys (use secure methods in production!)
# ------------------------------------------------------------------------------
# Either use st.secrets or environment variables.
NOTION_API_KEY = st.secrets.get("NOTION_API_KEY", "your-notion-api-key")
OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "your-openai-api-key")

# Initialize clients
notion = Client(auth=NOTION_API_KEY)
openai.api_key = OPENAI_API_KEY

# ------------------------------------------------------------------------------
# Helper Functions for Notion Parsing and Recursion
# ------------------------------------------------------------------------------

def extract_page_id(url: str) -> str:
    """
    Extracts the 32-digit page ID from a Notion URL and formats it as UUID.
    """
    patterns = [
        r'notion\.so/[^/]+/[^-]+-([a-f0-9]{32})',  # workspace/name-id format
        r'([a-f0-9]{32})',                          # direct ID
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            page_id = match.group(1)
            # Format as UUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
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
    # Try several field names in order
    for field in ["text", "rich_text", "title", "content"]:
        text = safe_get_text(block_content, field)
        if text:
            return text
    # Special handling for child_page
    if block_type == "child_page":
        return block_content.get("title", "")
    return ""

def process_block(block: Dict) -> str:
    """
    Process a block and returns its formatted content based on its type.
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
    # For child_page and child_database, processing happens separately.
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
                # Get a title for the entry (if available)
                page_title = ""
                for prop in entry.get("properties", {}).values():
                    if prop.get("type") == "title":
                        page_title = safe_get_text(prop, "title")
                        break
                if not page_title:
                    page_title = "Untitled"
                content.append(f"\n#### {page_title}\n")
                # Count this entry as a page
                if progress_callback:
                    progress_callback(1)
                entry_id = entry.get("id")
                # Recursively fetch block children for this page.
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
    
    When a child page is encountered, the progress_callback (if provided)
    is called to update the count.
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
            
            for block in blocks:
                block_type = block.get("type", "")
                
                # Handle child pages
                if block_type == "child_page":
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    page_title = block.get("child_page", {}).get("title", "Untitled")
                    content.append(f"\n### {page_title}\n")
                    # Update progress: count the child page
                    if progress_callback:
                        progress_callback(1)
                    child_page_id = block.get("id")
                    child_content = fetch_block_children(child_page_id, indent + 1, visited, progress_callback)
                    if child_content:
                        content.extend(child_content)
                    continue

                # Handle child databases by querying the embedded database
                if block_type == "child_database":
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    db_title = block.get("child_database", {}).get("title", "Database")
                    content.append(f"\n### Database: {db_title}\n")
                    database_id = block.get("id")
                    db_entries = fetch_database_entries(database_id, visited, progress_callback)
                    if db_entries:
                        content.extend(db_entries)
                    continue
                
                # Process regular blocks
                block_content = process_block(block)
                if not block_content:
                    continue

                # Group simple blocks together for readability.
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
                
                # If a block has children, fetch them recursively.
                if block.get("has_children", False):
                    if current_group:
                        content.append(" ".join(current_group))
                        current_group = []
                    child_content = fetch_block_children(block["id"], indent + 1, visited, progress_callback)
                    if child_content:
                        content.extend(child_content)
            
            if current_group:
                content.append(" ".join(current_group))
            
            if not response.get("has_more"):
                break
            cursor = response.get("next_cursor")
    except APIResponseError as e:
        logger.error(f"Error fetching blocks for id {block_id}: {str(e)}")
    return content

# ------------------------------------------------------------------------------
# Function to Query the OpenAI Agent with the Notion Content and a User Question
# ------------------------------------------------------------------------------
def query_chatgpt(content: str, question: str) -> str:
    """
    Sends the indexed Notion content and a question to OpenAI's Chat API.
    Each query is completely memoryless—only the current content and question are used.
    """
    try:
        prompt = (
            f"Below is the recursively indexed content of a Notion page (including subpages and database entries). "
            f"Analyze the content and answer the question that follows.\n\n"
            f"{content}\n\n"
            f"Question: {question}\n\n"
            f"Answer:"
        )
        messages = [
            {
                "role": "system",
                "content": "You are an expert document analyst. Answer questions based solely on the content provided."
            },
            {"role": "user", "content": prompt}
        ]
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Change to your desired model if needed
            messages=messages,
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error querying ChatGPT: {str(e)}")
        return f"Error querying ChatGPT: {str(e)}"

# ------------------------------------------------------------------------------
# Function to Fetch Notion Content with Progress Updates
# ------------------------------------------------------------------------------

def fetch_notion_content(notion_url: str, progress_callback: Optional[Callable[[int], None]] = None) -> str:
    """
    Given a Notion page URL, extract its content recursively and return as text.
    Progress updates (i.e. number of pages indexed) are provided via the progress_callback.
    """
    page_id = extract_page_id(notion_url)
    # Verify access to the page (this call also helps ensure that the integration has access)
    try:
        page = notion.pages.retrieve(page_id)
        # Get page title (if available)
        title = ""
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = safe_get_text(prop, "title")
                break
        st.info(f"Accessed page: {title or 'Untitled'}")
    except APIResponseError as e:
        raise Exception("Could not access the Notion page. Please ensure that the integration has been added to the page.")
    
    st.spinner("Fetching content from Notion...")
    content_blocks = fetch_block_children(page_id, visited=set(), progress_callback=progress_callback)
    if not content_blocks:
        return ""
    # Join the content blocks into one large text.
    return "\n\n".join(content_blocks)

# ------------------------------------------------------------------------------
# Streamlit UI with Progress Updates
# ------------------------------------------------------------------------------

def main():
    st.title("Notion Page QA with OpenAI (Memoryless Agent with Progress)")
    st.markdown(
        """
        This app lets you input a Notion page URL (with proper integration) and ask questions
        about its content. The page is recursively indexed, including any subpages or embedded databases.
        
        **Note:** The OpenAI agent is memoryless; each query is handled independently.
        A progress counter shows the number of pages indexed so far.
        """
    )

    notion_url = st.text_input("Enter Notion Page URL", placeholder="https://www.notion.so/your-page-url")
    
    # Create a progress counter and a placeholder to display progress.
    progress_state = {"count": 0}
    progress_placeholder = st.empty()
    
    def progress_callback(n: int):
        progress_state["count"] += n
        progress_placeholder.text(f"Indexed pages: {progress_state['count']}")
    
    if notion_url:
        try:
            with st.spinner("Loading Notion content..."):
                notion_content = fetch_notion_content(notion_url, progress_callback=progress_callback)
            if not notion_content:
                st.error("No content found in the page.")
            else:
                st.success("Content loaded successfully!")
                # Optionally display a snippet (or use an expander)
                with st.expander("Show Indexed Content (for debugging)"):
                    st.text_area("Indexed Content", notion_content, height=300)
                
                question = st.text_input("Ask a question about this page", placeholder="e.g., What is the main objective?")
                if st.button("Get Answer") and question.strip():
                    with st.spinner("Querying OpenAI..."):
                        answer = query_chatgpt(notion_content, question)
                    st.markdown("**Answer:**")
                    st.write(answer)
        except Exception as err:
            st.error(f"Error: {err}")

if __name__ == "__main__":
    main()
