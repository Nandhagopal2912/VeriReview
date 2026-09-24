def load(cfg):
    """Load settings from config."""
    return {k.lower(): v for k, v in cfg.items()}
