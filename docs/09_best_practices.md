md = """# Best Practices & Deployment Setup

To ensure the project remains secure, reproducible, and easy to run across different environments (especially Linux), we adhere to the following strict best practices for configuration and deployment.

## 1. Secrets Management (.env)
**NEVER** hardcode API keys or credentials into the Python source code. 
All secrets must be managed via environment variables using a `.env` file at the root of the project.

**Example `.env` file:**
```env
OPENAI_API_KEY=sk-proj-your-actual-api-key-here
```

*Note: We will use the `python-dotenv` library to load these variables automatically in local development.*

## 2. Source Control (.gitignore)
To prevent accidentally leaking secrets, committing massive cache files, or uploading virtual environments, the following strict `.gitignore` must be in place before the first commit.

**Essential `.gitignore` entries:**
```text
# Secrets
.env

# Python
__pycache__/
*.py[cod]
*$py.class
venv/
.venv/

# Local Project Cache (Crucial)
.cache/

# OS generated files
.DS_Store
```

## 3. Docker & Docker Compose
The entire application must be fully containerized. This ensures that the Python version, dependencies, and OS-level libraries (like those needed for `Textual` or `Rich`) are identical on every machine.

* **Dockerfile:** A lean Python image (e.g., `python:3.11-slim`) that installs `requirements.txt` and sets up the working directory.
* **compose.yaml:** We will use a modern Docker Compose setup to mount the local `.cache/` directory (so you don't lose your scraped data when the container stops) and inject the `.env` file.

*Important Note: Since you are using Linux, all documentation and scripts will use the modern `docker compose` command, completely avoiding the legacy `docker-compose` binary.*

## 4. Running Instructions
Whether running locally for rapid UI tweaking or via Docker for isolation, the project should be simple to boot up.

### Option A: Local Native (Best for TUI Development)
1. Create virtual environment: `python3 -m venv venv`
2. Activate: `source venv/bin/activate`
3. Install deps: `pip install -r requirements.txt`
4. Run: `python src/main.py` (or `python src/main.py --user 12345`)

### Option B: Docker (Best for clean environments)
1. Build and run interactively (so the TUI works):
   ```bash
   docker compose run --rm app
   ```
   *(Note: Because this is an interactive CLI app that requires terminal TTY access, we use `docker compose run` rather than `docker compose up -d` which runs in the background).*
"""