default:
    @just --list

# Install dependencies and git hooks.
install:
    uv sync --all-extras --all-groups
    uv run prek install
