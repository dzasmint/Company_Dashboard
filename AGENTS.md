# Repository Guidelines

## Project Structure & Module Organization
- `pages/`: Streamlit entry and page scripts (main: `Real_Estate_Financial_Model_God_AI.py`).
- `tabs/`: Feature modules loaded by pages (e.g., forecasting).
- `utils/`: Shared helpers (MongoDB, AI integrations, parsing).
- `core/`, `config/`: Domain logic and configuration constants.
- `data/`, `examples/`, `Bank_Sample/`: Sample datasets and inputs for local testing.
- `docs/`, `README.md`, `CLAUDE.md`: Reference documentation and workflows.

## Build, Test, and Development Commands
- Install deps: `pip install -r requirements.txt`.
- Run app: `streamlit run pages/Real_Estate_Financial_Model_God_AI.py`.
- Env setup: create `.env` (see `README.md`) with `MONGODB_CONNECTION_STRING`, `OPENAI_API_KEY`, `PERPLEXITY_API_KEY`.
- Optional data task: `python upload_moc_to_mongodb.py` to seed MoC data.

## Coding Style & Naming Conventions
- Python 3.10+; 4‑space indentation; limit lines to ~100 chars.
- Use type hints and concise docstrings for public functions.
- Modules: `snake_case.py`; classes: `PascalCase`; functions/vars: `snake_case`.
- Keep Streamlit UI in `pages/` or `tabs/`; keep I/O, API, and calculations in `utils/` or `core/`.
- Prefer small, testable functions; avoid side effects at import time.

## Testing Guidelines
- Current: no formal test suite. Validate changes via local runs and sample data in `data/` and `Bank_Sample/`.
- If adding tests, place under `tests/` with `test_*.py` (pytest style). Aim for coverage on utils/core logic and any non‑UI computations.
- Provide minimal fixtures or example inputs alongside tests.

## Commit & Pull Request Guidelines
- Commits: imperative present tense; be specific (e.g., `fix: correct leverage ratio calc`, `feat(utils): add RNAV parser`).
- Group related changes; avoid mixing refactors with behavior changes.
- PRs: include summary, rationale, screenshots for UI changes, repro/validation steps, and links to related issues/tasks. Note env vars or data prerequisites.

## Security & Configuration Tips
- Never commit secrets. Store API keys and DB URIs in `.env` (loaded via `python-dotenv`).
- Treat `data/` as non‑sensitive; scrub any confidential records before adding samples.
- External services used: OpenAI, Anthropic, Perplexity, MongoDB. Handle API failures gracefully and guard rate limits.

