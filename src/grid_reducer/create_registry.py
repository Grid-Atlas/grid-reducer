def make_registry():
    registry = {}

    def register(cls):
        def decorator(func):
            registry[cls] = func
            return func

        return decorator

    return registry, register
