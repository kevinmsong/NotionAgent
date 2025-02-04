# Notion Page QA (Memoryless) with Gemini 2.0 Flash

This Streamlit application fetches and indexes all blocks (and sub-pages/databases) from a specified Notion page, then uses **Gemini 2.0 Flash AI** (via `google.generativeai`) to answer questions about that Notion content. Both the Notion indexing and the AI prompt are done from scratch on each query—no content or AI context is cached or retained between sessions or questions.

## Features

- **Memoryless indexing**: Each time you click “Get Answer,” the Notion page is fully fetched (recursively through subpages and child databases) with no caching.
- **Memoryless AI**: Gemini 2.0 Flash AI sees only the single question and the Notion data at query time. No past interactions or user history is provided to the model.
- **Progress tracking**: A counter shows how many pages/entries have been indexed.
- **Debug-friendly**: You can optionally view the fully indexed content in a text area to see exactly what is being fed to the AI.

## Requirements

1. **Python 3.7+** (Recommended: Python 3.9 or newer).
2. Python libraries:
   - `streamlit`
   - `notion-client`
   - `google-generativeai`
   - Standard libraries (e.g. `logging`, `re`, `typing`) come with Python.
3. A **Notion integration token** with read access to your pages:
   - Create this under [Notion Integrations](https://www.notion.so/my-integrations).
   - Define it as an environment variable `NOTION_API_KEY` or store in `.streamlit/secrets.toml`.
4. A **Gemini API key** from [Google PaLM API](https://developers.generativeai.google/):
   - Define it as `gemini_api_key` in `.streamlit/secrets.toml` or an environment variable.

## Installation

```bash
pip install streamlit notion-client google-generativeai
