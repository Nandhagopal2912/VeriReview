class ConfigError(Exception):
    pass


def load_key(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except PermissionError as exc:
        raise ConfigError(f"cannot read key file {path}") from exc
