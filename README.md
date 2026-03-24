# Stips Profiler

An OSINT tool that analyzes user answers to build a comprehensive profile on them.

https://github.com/user-attachments/assets/cc88d22f-2e72-4192-898b-903d1f850ec7

## About the Project

Stips Profiler is an orchestration engine designed to transform unstructured, publicly available forum activity into structured intelligence. 

**Core Capabilities:**
* **Data Acquisition:** Scrapes a target's historical answers and persists them locally.
* **AI Analysis:** Utilizes large language models to parse unstructured text into a detailed profile.
* **Intelligence Extraction:** Autonomously identifies demographics, behavioral patterns, emotional states, and technical traits.
* **Rich Presentation:** Renders findings in a Terminal User Interface (TUI), complete with source evidence, temporal references, and activity heatmaps.

### The Development Process

This project was built primarily as a **system architecture and orchestration exercise** rather than a manual coding endeavor. 

* **Human-Driven Design:** The core architecture, data schemas, and API documentation were drafted manually to create strict engineering constraints.
* **AI-Assisted Implementation:** These constraints provided a precise context window for Claude 3 Opus, which generated the implementation across various domain-specific modules. 
* **Objective:** To prove the viability of building a robust, modular application through AI-assisted engineering and strict documentation constraints.

## Technical Architecture

The architecture is strictly divided into distinct operational layers:

* **Scraper Engine (`asyncio` / `httpx`)**
  * Handles paginated HTTP requests with exponential backoff.
  * Utilizes incremental scraping to bypass repetitive full-history pulls, stopping at previously cached answers.
* **Storage Layer (`sqlite3`)**
  * Manages local data persistence using parameterized queries.
  * Caches raw data and AI analysis results to ensure quick retrieval across sessions without unnecessary API calls.
* **AI Engine (`OpenAI API`)**
  * **Prompt Caching:** For accounts with smaller footprints, the system passes the full context window directly to leverage caching discounts.
  * **Embeddings (RAG):** For extensive user histories, the engine vectorizes answers and uses cosine similarity to retrieve only the most semantically relevant text chunks prior to LLM analysis.
* **Presentation (`Textual` / `Rich`)**
  * A responsive Python TUI featuring an interactive tree view.
  * Fully supports bidirectional (BiDi) text alignment for Hebrew.

## Why This Matters

This project serves as a practical demonstration of **Open Source Intelligence (OSINT)** and the concept of **"[data mosaic theory](https://en.wikipedia.org/wiki/Mosaic_effect)."**

* **The Premise:** Individually, forum posts are often innocuous—a casual clothing preference, a complaint about a delayed bus, or a passing comment about school. 
* **The Application:** When thousands of these granular data points are aggregated and processed through modern semantic analysis, they assemble into a highly accurate, intimate portrait of an individual's life. 
* **The Conclusion:** The ease with which this application constructs such profiles highlights both the impressive analytical capabilities of current AI models and the surprisingly vast digital footprint left behind by typical internet usage.

## Quick Start (Docker)

The application is fully containerized, eliminating the need for local Python environment configuration.

1.  **Environment Setup**:
    Clone the repository and copy the example environment file:
    ```bash
    git clone [https://github.com/VerifyBot/stips-profiler.git](https://github.com/VerifyBot/stips-profiler.git)
    cd stips-profiler
    cp .env.example .env
    ```
    Add your `OPENAI_API_KEY` to the `.env` file.

2.  **Build the Container**:
    ```bash
    docker compose build
    ```

3.  **Run the Profiler**:
    Execute the main interactive flow:
    ```bash
    docker compose run --rm app python -m src.main
    ```
    Or run it headlessly for a specific target ID:
    ```bash
    docker compose run --rm app python -m src.main --user 123456
    ```

### Development & Testing

To run the (partial) automated test suite inside the container:
```bash
docker compose run --rm app python test_live.py
docker compose run --rm app python test_offline.py