md = """# Terminal UI (TUI) & User Flow

The application uses `Rich` for linear, beautiful CLI outputs (progress bars, colorful tables) and `Textual` for the final interactive dashboard. The flow is designed to maximize perceived speed and user control.

## Entry Points

The app supports both interactive and direct CLI executions:

* **Interactive:** `python main.py` (Boots to Screen 1)

* **Direct:** `python main.py --user 12345` (Skips to Screen 2)

## Step-by-Step Flow

### Screen 1: The Boot Up (Rich)

* Terminal clears. Displays colorful ASCII art logo.

* Prompt: `> Enter Stips User ID or Profile URL:`

### Screen 2: The Fast Pre-Check (Rich)

* **Action:** The scraper makes *one* fast API request to get the user's metadata and total "flowered" response count. No heavy text is downloaded yet.

* **Display:** A bordered info box appears.

  ```
  ╭────────────────────────────────────────╮
  │ User Target: @sneakerhead_telaviv      │
  │ Flowered Responses Found: 412          │
  │ Estimated Token Size: ~18,500 tokens   │
  ╰────────────────────────────────────────╯
  
  ```

### Screen 3: Engine Selection (Rich Interactive)

* The user selects how to process the data based on the count.

  ```
  > Select AI Processing Engine:
    [ ] Prompt Caching + Few-Shot  <----- (Recommended for < 300 answers)
    [x] Embeddings Vector Search   <----- (Recommended for > 300 answers)
  
  ```

### Screen 4: The Heavy Lift & Fancy Loading (Rich)

* **Action:** Now that the user has committed, the system downloads the actual text responses.

* **Display:** Live, dynamic terminal spinners and progress bars that update in place.

  * `[✓] Fetching 412 responses from Stips API... (Loaded from Local Cache)` *<-- If cached*

  * `[✓] Generating vector embeddings (412/412)`

  * `[⠧] LLM extracting facts (Topic: Education & Career)...` *(Spinner animates)*

### Screen 5: The Interactive Dashboard (Textual)

* The linear terminal clears, replaced by a full-screen `Textual` TUI (Terminal User Interface).

* **Navigation:** Fully navigable via `Up/Down/Left/Right` arrow keys or Mouse Clicks.

**Left Panel (The Category Tree):**
An interactive directory tree of the user's life.

```
▼ 👤 Personal & Demographic
  ├── Age & Location (3 facts)
  └── Military / IDF (2 facts)
▶ 🎓 Education & Career
▼ 🎸 Interests & Beliefs
  ├── K-Pop Obsession (4 facts)

```

**Right Panel (Context & Evidence):**
Dynamically updates based on the highlighted node on the left.

```
[ CATEGORY: K-Pop Obsession ]

🧠 AI Summary:
User is a massive fan of the band Stray Kids and attends local fan events.

🔗 Source Evidence (Stips Quotes):
1. "תקשיבי הייתי בהופעה שלהם שנה שעברה והיה מטורף" 
2. "פליקס פשוט מושלם אין מה לעשות"

```

### Screen 6: Footer Options

* A sticky footer at the bottom: `[E]xport to JSON` | `[C]lear Cache` | `[Q]uit`.
"""