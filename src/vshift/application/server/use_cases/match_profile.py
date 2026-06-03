from loguru import logger

from vshift.application.server.use_cases.models import ProfileMatch
from vshift.domain.config.enums import NoMatchAction
from vshift.domain.file.probed_input import ProbedInput
from vshift.exception import VShiftException
from vshift.ports.config_repository import ConfigRepository


class MatchProfile:
    """Resolves the transcoding profile for a probed input file."""

    def __init__(self, config_repository: ConfigRepository) -> None:
        self._config_repository = config_repository

    def execute(self, probed: ProbedInput) -> ProfileMatch | None:
        config = self._config_repository.get_config()
        rule = config.create_profile_matcher().match(probed)
        if rule is not None:
            profile = config.profiles[rule.profile]
            return ProfileMatch(
                rule_id=rule.id,
                profile_name=rule.profile,
                profile=profile,
            )

        behavior = config.behavior
        if behavior.no_match == NoMatchAction.IGNORE:
            logger.debug("no profile match for {}", probed.path)
            return None

        if behavior.no_match == NoMatchAction.REJECT:
            logger.warning("rejected input without profile match: {}", probed.path)
            return None

        if behavior.default_profile is None:
            msg = "default_profile is required when no_match is default_profile"
            raise VShiftException(msg)

        profile = config.profiles[behavior.default_profile]
        return ProfileMatch(
            rule_id="__default__",
            profile_name=behavior.default_profile,
            profile=profile,
        )
