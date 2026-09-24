class Plugin:
    def handler(self, event):
        return event.upper()


def dispatch(plugin, event):
    return getattr(plugin, "handler")(event)
