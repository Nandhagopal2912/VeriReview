def load(cfg):
    """Load settings from cfg."""
    return {k.lower(): v for k, v in cfg.items()}
