md = """# Stips User Profiler: Project Overview & AI Architecture

## The Concept
An automated psychological and demographic profiling tool built for the Israeli Q&A platform, Stips. By analyzing a user's "flowered" (OP-voted/upvoted) responses, the system extracts implicit and explicit personal facts to build a comprehensive user profile.

The final output is rendered in an advanced, visually appealing Python terminal UI (CLI) that displays the user's life categorized into a navigable tree structure.

## The Challenge
* **High Noise-to-Signal Ratio:** 90% of a user's answers are generic advice or conversational filler. Only a fraction contains actual personal facts (e.g., age, hobbies, struggles).
* **"Lost in the Middle" Phenomenon:** Dumping 1,000 responses into a single LLM prompt causes the AI to ignore details buried in the middle of the text.
* **Language & Nuance:** The data is entirely in Hebrew, heavily peppered with teen slang, typos, and specific Israeli cultural contexts (Bagrut exams, Tzav Rishon, IDF drafts, Rav-Kav, etc.).

## The Solution: Intelligent Extraction
Instead of a single massive prompt, we use an architectural pattern designed to filter noise first, and compile facts second. 

### Recommended LLMs for Hebrew & Slang
* **Primary (Compilation/Reasoning):** OPENAI (Best for "reading between the lines" and outputting strict JSON).
* **Secondary (Fast Batch Filtering):** OPENAI
"""