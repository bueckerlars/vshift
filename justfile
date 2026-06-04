default:
    @just --list

docker-image := "ghcr.io/bueckerlars/vshift"

# Install dependencies and git hooks.
install:
    uv sync --all-extras --all-groups
    uv run prek install

# Build the release image locally for the current platform (server and worker use the same image).
docker-build:
    docker build \
        -t {{docker-image}}:latest \
        -t {{docker-image}}:`git describe --tags --always --dirty` \
        --label org.opencontainers.image.description="Automatic FFmpeg-based video transcoder" \
        .

# Build and push a multi-arch image (linux/amd64 + linux/arm64). Requires `docker buildx` and `docker login ghcr.io`.
docker-build-push tag:
    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        --push \
        -t {{docker-image}}:{{tag}} \
        -t {{docker-image}}:latest \
        --label org.opencontainers.image.description="Automatic FFmpeg-based video transcoder" \
        .
