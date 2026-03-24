# Stips Profiler

A modular OSINT tool that extracts, caches, and analyzes public Q&A data to build comprehensive psychological and demographic profiles.

https://www.youtube.com/watch?v=GjZr-MDL2OM


## About the Project

Stips Profiler is an orchestration engine designed to transform unstructured, publicly available forum activity into structured intelligence. It scrapes a target's historical answers, stores them locally, and uses large language models to construct a detailed profile—identifying demographics, behavioral patterns, emotional states, and technical traits. 

The application presents these findings in a rich Terminal User Interface (TUI), complete with source evidence, temporal references, and activity heatmaps.

### The Development Process

This project was built primarily as a system architecture and orchestration exercise rather than a manual coding endeavor. The core design, data schemas, and API documentation were drafted manually, providing a strict context window for Claude 3 Opus. The LLM then generated the implementation across various domain-specific modules. The objective was to build a robust tool through AI-assisted engineering and precise documentation constraints.

## Technical Architecture

The architecture is divided into distinct operational layers:

*   **Scraper Engine (`asyncio` / `httpx`)**: Handles paginated HTTP requests with exponential backoff and incremental scraping. Bypasses repetitive full-history pulls by stopping at previously cached answers.
*   **Storage Layer (`sqlite3`)**: Manages local data persistence. Uses parameterized queries to store raw data and AI analysis results, ensuring quick retrieval across sessions without unnecessary API calls.
*   **AI Engine (`OpenAI API`)**: 
    *   **Prompt Caching**: For accounts with smaller footprints, passes the full context window directly.
    *   **Embeddings (RAG)**: For extensive user histories, vectorizes answers and uses cosine similarity to retrieve only the most semantically relevant text chunks prior to LLM analysis.
*   **Presentation (`Textual` / `Rich`)**: A responsive Python TUI featuring an interactive tree view, bidirectional (BiDi) text alignment for Hebrew, chronological heatmaps, and clickable source citations.

## Why This Matters

This project serves as a practical demonstration of Open Source Intelligence (OSINT) and the concept of "[data mosaic theory](https://en.wikipedia.org/wiki/Mosaic_effect)."

Individually, forum posts are often innocuous—a casual clothing preference, a complaint about a delayed bus, or a passing comment about school. However, when thousands of these granular data points are aggregated and processed through modern semantic analysis, they assemble into a highly accurate, intimate portrait of an individual's life. 

The ease with which this application constructs such profiles highlights both the impressive analytical capabilities of current AI models and the surprisingly vast digital footprint left behind by typical internet usage.

## Quick Start (Docker)

The application is fully containerized, eliminating the need for local Python environment configuration.

1.  **Environment Setup**:
    Clone the repository and copy the example environment file:
    ```bash
    git clone https://github.com/VerifyBot/stips-profiler.git
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
```

If you modify dependencies in `requirements.txt`, rebuild the image:
```bash
docker compose build
```