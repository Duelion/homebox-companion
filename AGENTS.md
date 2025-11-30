# Agent Guidelines
- Target the Homebox **demo** API at `https://demo.homebox.software/api/v1` using the demo credentials (`demo@example.com` / `demo`). Do not reference or use the duelion production environment.
- Manage Python tooling with **uv**: create a virtual environment via `uv venv`, add dependencies with `uv add`, and run scripts with `uv run`. Keep dependencies tracked in `pyproject.toml` and `uv.lock`.
- When testing functionality, hit the real demo API rather than mocks or stubs.
