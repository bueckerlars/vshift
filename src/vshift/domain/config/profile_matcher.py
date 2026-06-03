from vshift.domain.config.match_rule import MatchRule
from vshift.domain.file.probed_input import ProbedInput


class ProfileMatcher:
    """Selects the first matching rule by ascending priority."""

    def __init__(self, rules: list[MatchRule]) -> None:
        self._rules = sorted(rules, key=lambda rule: rule.priority)

    def match(self, probed: ProbedInput) -> MatchRule | None:
        for rule in self._rules:
            if rule.matches(probed):
                return rule
        return None
