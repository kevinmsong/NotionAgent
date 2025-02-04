# Notion Page QA with OpenAI (Memoryless Agent with Progress)

This Streamlit app enables you to interactively query the content of any Notion page using an OpenAI-powered agent. The app recursively indexes the entire Notion page—including subpages and embedded databases—while displaying a real-time progress indicator that shows the number of pages indexed. Each query is handled independently, ensuring that the agent is memoryless and does not retain any context between queries.

## Features

- **Recursive Indexing:**  
  Retrieves and processes content from a Notion page, including any nested subpages and embedded databases, for comprehensive querying.

- **Memoryless Agent:**  
  Each query to OpenAI is processed as a standalone interaction. The agent sees only the freshly indexed content along with the current question, with no memory of prior exchanges.

- **Real-Time Progress Updates:**  
  A live progress counter displays the number of Notion pages that have been indexed during the retrieval process, offering transparency into the indexing workflow.

- **Interactive User Interface:**  
  Built with Streamlit, the app provides a user-friendly interface where you can input a Notion URL, preview indexed content, and ask questions about the page.
