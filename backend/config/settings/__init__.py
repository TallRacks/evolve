import environ

env = environ.Env(EVOLVE_ENV=(str, "development"))
environment = env("EVOLVE_ENV").lower()

if environment == "production":
    from .production import *  # noqa: F403
elif environment == "test":
    from .test import *  # noqa: F403
else:
    from .development import *  # noqa: F403
