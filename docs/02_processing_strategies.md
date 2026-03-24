md = """# AI Processing Strategies & User Flow

When a user is queried via the Stips API, the system checks their total "flowered" response count. Based on this volume, the CLI will present the user with two processing engines, dynamically recommending the best one.

## The CLI Prompt
```text
Found User: [Username]
Total Flowered Responses: [Count]

What engine do you want to use?
1. Prompt Caching + Few-Shot Prompting  <----- (recommended if < 300 answers)
2. Embeddings Vector Search + LLM        <----- (recommended if > 300 answers)
```

## Strategy 1: Prompt Caching + Few-Shot (For < 300 Responses)
**Best for:** Low-to-medium volume users.
**How it works:**
1. Load all responses into the LLM's context window.
2. Use **Prompt Caching** (available via OpenAI/Anthropic/Google) to save the computed state of the text.
3. Run rapid, parallel queries against the cached text (e.g., "Extract family info", "Extract school info"). This is 50-80% cheaper and runs in milliseconds.
4. Use **Few-Shot Prompting** in the system instructions to teach the AI the slang. 
   * *Example Input:* "אחי עזוב אותי יש לי מגן במתמטיקה מחר ואין לי כוח לזה, הוצאתי 60 במועד א"
   * *Example Output:* `[{"fact": "Struggles with math", "context": "Got a 60 on Moed A, stressed about Magen"}]`

## Strategy 2: Embeddings + LLM (For > 300 Responses)
**Best for:** Power users with thousands of responses.
**How it works (Retrieval-Augmented Generation - RAG):**
1. Convert all answers into vectors using an embedding model (e.g., `text-embedding-3-small`).
2. Embed our target concepts (e.g., "Family", "School", "Hobbies").
3. Use vector math (cosine similarity) to find the top 20-50 answers that semantically align with the targets.
4. Pass *only* those highly relevant answers to the LLM for extraction, saving massive amounts of tokens and preventing hallucinations.
"""