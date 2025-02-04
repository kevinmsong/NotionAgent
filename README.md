# Notion Page QA with Gemini 2.0 Flash

This Streamlit-based application lets you query the content of any Notion page using Google Gemini 2.0 Flash AI. The app recursively indexes the entire Notion page—including subpages and embedded databases—and then uses Gemini 2.0 Flash to generate an answer based on the indexed content.

## Features

- **Recursive Notion Indexing:**  
  The application crawls and converts the content of a Notion page (including subpages and embedded databases) into a unified text document.

- **Gemini 2.0 Flash AI Integration:**  
  Instead of using OpenAI's Chat API, the app leverages Google’s Gemini 2.0 Flash AI (via the `google-generativeai` package) to generate responses.

- **Cached Content:**  
  Indexed content is stored in Streamlit's session state so that the Notion page is only indexed once per URL—even if multiple questions are asked.

- **Progress Feedback:**  
  A live progress counter shows the number of pages indexed during the recursive retrieval process.

- **User-Friendly Interface:**  
  With a simple UI for entering a Notion page URL and asking questions, you can quickly retrieve and analyze page content.
  
