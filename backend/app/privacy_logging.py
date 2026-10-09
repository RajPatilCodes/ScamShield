import logging

PRIVATE_PREFIXES = ("/v1/auth/", "/v1/privacy", "/analysis/")


class PrivateAccessFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, target, version, status = record.args
            if isinstance(target, str) and target.startswith(PRIVATE_PREFIXES):
                record.args = (client, method, "[private-route]", version, status)
        return True


def install_redaction():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, PrivateAccessFilter) for item in logger.filters):
        logger.addFilter(PrivateAccessFilter())
