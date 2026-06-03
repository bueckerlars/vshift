default:
    @just --list

docker-image := "ghcr.io/bueckerlars/vshift"

# Install dependencies and git hooks.
install:
    uv sync --all-extras --all-groups
    uv run prek install

# Build the release image locally (server and worker use the same image).
docker-build:
    docker build \
        -t {{docker-image}}:latest \
        -t {{docker-image}}:`git describe --tags --always --dirty` \
        --label org.opencontainers.image.description="Automatic FFmpeg-based video transcoder" \
        .
