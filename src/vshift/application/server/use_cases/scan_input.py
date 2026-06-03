from pathlib import Path

from loguru import logger

from vshift.application.server.use_cases.enqueue_job import EnqueueJob
from vshift.application.server.use_cases.match_profile import MatchProfile
from vshift.application.server.use_cases.probe_input_file import ProbeInputFile
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.ports.config_repository import ConfigRepository
from vshift.ports.file_scanner import FileScanner


class ScanInputFolder:
    """Scans the input directory and enqueues jobs for stable, matched files."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        file_scanner: FileScanner,
        probe_input_file: ProbeInputFile,
        match_profile: MatchProfile,
        enqueue_job: EnqueueJob,
    ) -> None:
        self._config_repository = config_repository
        self._file_scanner = file_scanner
        self._probe_input_file = probe_input_file
        self._match_profile = match_profile
        self._enqueue_job = enqueue_job

    def execute(self, input_dir: Path | None = None) -> list[TranscodeJob]:
        config = self._config_repository.get_config()
        scan_dir = input_dir or config.directories.input
        enqueued: list[TranscodeJob] = []

        for candidate in self._file_scanner.scan_once(scan_dir):
            probed = self._probe_input_file.execute(candidate)
            match = self._match_profile.execute(probed)
            if match is None:
                continue

            job = self._enqueue_job.execute(probed, match)
            if job is not None:
                enqueued.append(job)

        logger.info(
            "scan completed for {}: {} job(s) enqueued",
            scan_dir,
            len(enqueued),
        )
        return enqueued
