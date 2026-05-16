# Contributing

Thanks for your interest in contributing to this project.

## What this project is

This is a research-grade UBA (User Behavior Analytics) system built on the CERT Insider Threat Dataset r4.2. It uses LSTM Autoencoders, Isolation Forest, and a contextual risk scoring engine to detect insider threats. Contributions should align with that scope.

## Getting started

1. Fork the repo and clone it locally
2. Set up the Python environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate       # Windows
   source .venv/bin/activate    # macOS/Linux
   pip install -r requirements.txt
   ```
3. Set up the frontend:
   ```bash
   cd website
   npm install
   ```

## Making changes

- Keep PRs focused — one fix or feature per PR
- For new ML models or pipeline changes, include updated evaluation results
- For API changes, update the relevant Pydantic schemas in `src/api/schemas/`
- For frontend changes, test against the live backend before submitting

## Running tests

```bash
pytest tests/ -v
```

All existing tests must pass before a PR can be merged.

## Submitting a PR

1. Create a branch: `git checkout -b your-feature-name`
2. Commit with a clear message: `git commit -m "what and why"`
3. Push and open a Pull Request against `main`
4. Describe what you changed and why in the PR description

## What not to contribute

- Do not commit `.env` files, trained model binaries (`.joblib`, `.pt`), or generated data files
- Do not add new root-level scripts without discussion — the project structure is intentional
