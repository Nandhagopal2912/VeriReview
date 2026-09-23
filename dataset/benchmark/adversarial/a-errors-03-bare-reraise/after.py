def setting(settings, name, default):
    try:
        return settings[name]
    except KeyError:
        raise
