from vshift.domain.file.probed_input import ProbedInput
from vshift.ports.media_prober import MediaProber


class ProbeInputFile:
    """Reads ffprobe metadata for an input file."""

    def __init__(self, media_prober: MediaProber) -> None:
        self._media_prober = media_prober

    def execute(self, candidate: ProbedInput) -> ProbedInput:
        probed = self._media_prober.probe(candidate.path)
        if candidate.extension:
            return probed.model_copy(update={"extension": candidate.extension})
        return probed
