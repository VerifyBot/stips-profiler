md = """# Data Schema & Categorization Strategy

To ensure the terminal UI can render a beautiful, collapsible tree, the data structure must be somewhat predictable at the root level, but highly dynamic at the leaf level to capture the unique essence of each user.

## The Approach: "Fixed Trunks, Dynamic Branches"
We provide the LLM with hardcoded top-level categories, but instruct it to *invent* the sub-categories based on the actual extracted facts. 

### The Fixed Trunks (Top Level)
* `Personal & Demographic`
* `Education & Career`
* `Social & Family`
* `Interests & Beliefs`

### System Prompt Instruction
*"Sort the user's facts into the 4 main buckets provided. For each fact, create a highly specific, dynamic sub-category based on their actual life. Do not use generic sub-categories (e.g., use 'Bagrut Struggles' instead of 'School')."*

### Target JSON Output Schema
```json
{
  "Education & Career": {
    "Bagrut Struggles": [
      "Got a 60 in Math Moed A, stressed about the Magen.",
      "Studying 5 units of English."
    ],
    "Part-Time Jobs": [
      "Works at a local cafe in Petah Tikva."
    ]
  },
  "Interests & Beliefs": {
    "K-Pop Obsession": [
      "Huge fan of Stray Kids.",
      "Went to a concert last year."
    ],
    "Mechanical Keyboards": [
      "Spends too much money on custom switches."
    ]
  }
}
```
"""