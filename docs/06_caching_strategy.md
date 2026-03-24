md = """# Local Caching & Data Management

To prevent unnecessary API calls, avoid rate-limiting, and speed up development iterations, the system implements a robust local caching layer.

## Caching Rules
1. **Raw Stips Responses:** ALWAYS CACHED. Once downloaded, they are stored locally. Future runs on the same User ID will load from disk instantly.
2. **Vector Embeddings:** ALWAYS CACHED. Embedding 1,000 strings costs money and time. If the raw responses haven't changed, load embeddings from disk.
3. **LLM Outputs / Profiling:** NOT CACHED (Yet). Because prompt engineering is an iterative process, we want the LLM to run fresh every time during development so we can see how prompt tweaks change the output.

## Storage Format
Local data is stored in a hidden `.cache/` directory in the project root, using either structured JSON files or a lightweight SQLite database.

**Directory Structure:**
```text
.cache/
├── users/
│   ├── 12345_meta.json       (Stores username, flower count)
│   └── 12345_responses.json  (Stores the array of raw Q&A text)
└── embeddings/
    └── 12345_embeddings.npz  (Stores the NumPy arrays of vector data)
```

## Cache Invalidation
The CLI allows users to bypass the cache if they suspect the Stips user has posted new answers since the last run.
* CLI Arg: `python main.py --user 12345 --force-refresh`
* TUI Footer: Pressing `[C]` clears the current user's cache and triggers a fresh scrape.
"""