md = """# Modular Project Architecture

The codebase is strictly separated by domain. This allows independent development and testing of the UI, the Scraper, and the AI components without breaking the rest of the app.

## Directory Tree

```text
stips_profiler/
│
├── .cache/                     # Local data storage (ignored in git)
├── docs/                       # Architecture documentation (MD files)
├── requirements.txt            # Python dependencies
│
├── src/                        # Main source code
│   ├── __init__.py
│   ├── main.py                 # The orchestrator (CLI entry point)
│   │
│   ├── scraper/                # Domain 1: Data Acquisition
│   │   ├── __init__.py
│   │   ├── client.py           # Handles Stips HTTP requests (no AI logic)
│   │   └── parsers.py          # Cleans raw HTML/JSON into standard dicts
│   │
│   ├── cache/                  # Domain 2: Data Persistence
│   │   ├── __init__.py
│   │   └── storage.py          # Handles read/write to the .cache/ folder
│   │
│   ├── ai/                     # Domain 3: Intelligence
│   │   ├── __init__.py
│   │   ├── prompts.py          # Stores System Instructions & Few-Shot examples
│   │   ├── embeddings.py       # Handles vector generation and K-Means clustering
│   │   └── engines.py          # Interfaces with OpenAI API
│   │
│   └── ui/                     # Domain 4: Presentation
│       ├── __init__.py
│       ├── cli_flow.py         # The linear Rich setup screens (Screens 1-4)
│       └── dashboard.py        # The interactive Textual app (Screen 5)
```

## Modularity Rules
1. **The Scraper** knows nothing about AI or the UI. It simply takes a User ID and returns a List of dictionaries.
2. **The AI Engine** knows nothing about Stips. It simply takes a List of strings and returns a categorized JSON tree.
3. **The UI** knows nothing about APIs. It simply takes the finalized JSON tree and renders it.
4. **`main.py`** acts as the Traffic Cop. It calls the Scraper, passes the data to the Cache, passes the cached data to the AI, and passes the AI output to the UI.
"""