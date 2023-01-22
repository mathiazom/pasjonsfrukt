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
        record.args = tuple(self._redacted_string(a) if isinstance(a, str) else a for a in record.args)
        return True
