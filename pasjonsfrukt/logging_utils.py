import logging


class LogRedactSecretFilter(logging.Filter):
    def __init__(self, secrets: list[str], redact_string: str = "******"):
        super().__init__()
        self.secrets = secrets
        self.redact_string = redact_string

    def _redacted_string(self, s) -> str:
        redacted = s
        for s in self.secrets:
            redacted = redacted.replace(s, self.redact_string)
        return redacted

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._redacted_string(record.msg)
        record.args = tuple(
            self._redacted_string(a) if isinstance(a, str) else a for a in record.args
        )
        return True


def get_logging_level(verbosity: int, debug: bool) -> int:
    if debug:
        verbosity = 4

    level = logging.INFO
    if verbosity >= 4:
        level = 1  # aka SPAM
    elif verbosity == 3:
        level = logging.DEBUG  # 10
    elif verbosity == 2:
        level = 15  # 15
    elif verbosity == 1:
        level = logging.INFO  # 20
    elif verbosity == -1:
        level = logging.WARNING  # 30
    elif verbosity < -1:
        level = logging.ERROR  # 40
    return level
