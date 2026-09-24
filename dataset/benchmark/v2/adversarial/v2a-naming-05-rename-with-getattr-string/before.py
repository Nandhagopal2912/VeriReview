class Plugin:
    def hndl(self, event):
        return event.upper()


def dispatch(plugin, event):
    return getattr(plugin, "hndl")(event)
