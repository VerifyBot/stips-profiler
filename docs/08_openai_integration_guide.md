# API Provider Decision & Cost Analysis

## Selected Provider: OpenAI

After evaluating Anthropic (Claude), Google (Gemini), and OpenAI based on Hebrew language capabilities, JSON structuring reliability, and API costs, **OpenAI** was selected as the sole provider for the Stips Profiler.

### The Selected Stack
* **Primary LLM Engine:** `gpt-5.4-nano`
  * *Role:* Reading raw text, filtering noise, and outputting the final JSON category tree.
  * *Why:* It is OpenAI's cheapest GPT-5.4-class model designed specifically for simple, high-volume tasks. It supports strict "Structured Outputs" and has incredibly aggressive prompt caching discounts.
* **Embeddings Engine:** `text-embedding-3-small`
  * *Role:* Converting text to vectors for semantic search on high-volume users (> 300 responses).
  * *Why:* Industry standard, seamlessly integrates with the same API key/client, and costs virtually nothing.

### Cost Analysis (Per Heavy User with gpt-5.4-nano)
Hebrew requires roughly 1.5 - 2 tokens per word. 
* **Scenario:** A heavy user with 1,000 responses (~20,000 words -> ~40,000 tokens).
* **Embedding Cost:** 40,000 tokens @ $0.02/1M = **$0.0008**
* **LLM Input Cost (Uncached Baseline):** 40,000 tokens @ $0.20/1M = **$0.008**
* **LLM Input Cost (Cached - parallel UI calls):** 40,000 tokens @ $0.02/1M = **$0.0008**
* **LLM Output Cost (JSON):** ~2,000 tokens @ $1.25/1M = **$0.0025**
* **Total Estimated Cost:** **~ $0.0113 (Just over 1 cent per user)**

Because of the $0.02/1M cached input pricing on `gpt-5.4-nano`, we can run rapid, parallel queries against the user's data to build the UI instantly without worrying about multiplying input costs!

md = """# OpenAI API Integration & Usage Guide

This document outlines the exact API methods, models, and Python code structures we will use to interface with OpenAI. It utilizes the latest OpenAI Python SDK features (Pydantic Structured Outputs and Automatic Prompt Caching).

## 1. Environment Setup
**Prerequisites:**
```bash
pip install openai pydantic numpy
```

**Initialization:**
```python
from openai import OpenAI
import os

# Initializes automatically using the OPENAI_API_KEY environment variable
client = OpenAI() 
```

---

## 2. Generating the JSON Tree (Structured Outputs)
To ensure our terminal UI never crashes from bad JSON, we use OpenAI's `beta.chat.completions.parse` method combined with `Pydantic`. This forces `gpt-5.4-nano` to return an object that perfectly matches our Python classes.

**The Schema Definition:**
```python
from pydantic import BaseModel
from typing import List

class ExtractedFact(BaseModel):
    fact: str
    source_quote: str # The original Stips Hebrew text for the UI right-panel

class DynamicCategory(BaseModel):
    category_name: str # e.g., "Bagrut Struggles" or "K-Pop Obsession"
    facts: List[ExtractedFact]

class UserProfileTree(BaseModel):
    personal_and_demographic: List[DynamicCategory]
    education_and_career: List[DynamicCategory]
    social_and_family: List[DynamicCategory]
    interests_and_beliefs: List[DynamicCategory]
```

**The API Call:**
```python
def extract_profile(stips_responses: List[str]) -> UserProfileTree:
    system_prompt = "You are a psychological profiler. Read the following Stips answers and extract facts..."
    user_content = "\\n".join(stips_responses)

    completion = client.beta.chat.completions.parse(
        model="gpt-5.4-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        response_format=UserProfileTree, # <--- MAGIC HAPPENS HERE
    )

    # Returns a fully typed, validated Python object (not just a string!)
    return completion.choices[0].message.parsed
```

---

## 3. Generating Vector Embeddings (For >300 Responses)
When a user has too many responses, we embed them to perform a semantic search before sending them to the LLM.

**The API Call:**
```python
def get_embeddings(texts: List[str]) -> List[List[float]]:
    # text-embedding-3-small is incredibly cheap ($0.02 / 1M tokens)
    response = client.embeddings.create(
        input=texts,
        model="text-embedding-3-small"
    )
    
    # Returns a list of vectors (arrays of floats)
    return [data.embedding for data in response.data]
```
*Note: To find the most relevant answers, we will use `numpy` to calculate the cosine similarity between the embedded Stips answers and our target categories (e.g., embedding the word "School" and finding the closest answer vectors).*

---

## 4. Leveraging Prompt Caching (Cost/Speed Optimization)
**How it works in OpenAI:** You do *not* need a specific API parameter to turn on Prompt Caching. OpenAI does it automatically for any prompt prefix longer than 1,024 tokens. 

**How we utilize it:**
With `gpt-5.4-nano`, cached input drops from $0.20/1M to an incredible $0.02/1M. To get this discount, we must structure our messages array so the longest, most static part (The System Prompt + The Few-Shot Examples + The massive list of Stips answers) is at the *very beginning* of the prompt.

If we make multiple calls for the same user (e.g., splitting the categorization into 4 parallel API calls to make the UI load faster), OpenAI will automatically recognize the first ~18,000 tokens are identical and serve them from cache in milliseconds!

```python
# Optimal caching structure
messages = [
    {"role": "system", "content": "HEAVY STATIC PROMPT WITH EXAMPLES..."}, # Cached @ $0.02/1M
    {"role": "user", "content": "MASSIVE STIPS DATA DUMP..."},             # Cached @ $0.02/1M
    {"role": "user", "content": "Now, extract only the 'Education' facts."} # Computed fresh @ $0.20/1M
]
```
"""