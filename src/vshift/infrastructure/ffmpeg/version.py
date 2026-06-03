import re
import subprocess


def ffmpeg_version(ffmpeg_path: str) -> str:
    completed = subprocess.run(
        [ffmpeg_path, "-version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return "unknown"

    lines = completed.stdout.splitlines()
    if not lines:
        return "unknown"

    match = re.search(r"ffmpeg version (\S+)", lines[0])
    if match is None:
        return "unknown"
    return match.group(1)
