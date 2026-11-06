# NotionAgent

Memoryless Streamlit Q&A over a Notion page using Gemini 2.0 Flash. Every answer re-fetches and re-indexes the page (including subpages and child databases); nothing is cached between questions.

## Features

- Recursive Notion indexing (blocks, child pages, child databases)
- Gemini 2.0 Flash answers from the freshly indexed text only
- Progress counter for indexed pages/entries
- Optional expander to inspect the indexed content fed to the model

## Requirements

See `requirements.txt`:

- streamlit
- notion-client
- google-generativeai
- openai (listed in requirements; the app path shown uses Gemini)

Also need:

- A Notion integration token with read access to the target page
- A Gemini API key

## Setup

1. Clone the repo and install deps:

```bash
pip install -r requirements.txt
```

2. Configure Streamlit secrets (e.g. `.streamlit/secrets.toml`):

```toml
NOTION_API_KEY = "YOUR_NOTION_INTEGRATION_TOKEN"
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"
```

3. Share the Notion page with your integration.

## Usage

```bash
streamlit run NotionAgent.py
```

Then paste a Notion page URL, ask a question, and click **Get Answer**.

## Notes

- Keys are read from `st.secrets` (`NOTION_API_KEY`, `GEMINI_API_KEY`). Do not hardcode tokens in source.
- Default placeholder Notion key in code is only a fallback string; set secrets before use.
