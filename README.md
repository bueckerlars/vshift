# vshift

## Requirements

- [Python](https://www.python.org/) 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency management

Development setup additionally uses [just](https://github.com/casey/just) for common tasks.

## Production installation

Install runtime dependencies only (no dev tools or git hooks):

```bash
uv sync
```

Run the CLI:

```bash
uv run vshift
```

To install the package into the active environment without `uv run`:

```bash
uv sync
uv pip install -e .
vshift
```

For deployment or CI, prefer a locked install from `uv.lock`:

```bash
uv sync --locked
```

## Development installation

Install all dependency groups (including `dev`), optional extras, and git hooks:

```bash
just install
```

Equivalent manual steps:

```bash
uv sync --all-extras --all-groups
uv run prek install
```

This creates a virtual environment in `.venv`, installs [prek](https://github.com/j178/prek) and [Ruff](https://docs.astral.sh/ruff/), and registers pre-commit hooks (Ruff lint/format, YAML/TOML checks, and more — see `.pre-commit-config.yaml`).

### Without just

If you do not use `just`, run the commands above directly. You only need `just` for the `install` recipe; everything else works with `uv` and `uv run`.

### Git hooks

Hooks run automatically on `git commit`. To run them manually:

```bash
uv run prek run          # staged files
uv run prek run --all-files
```

### Linting and formatting

```bash
uv run ruff check src
uv run ruff format src
```

## Project layout

```
src/vshift/    Application code
pyproject.toml Dependencies and tool configuration
justfile       Development task shortcuts
```
