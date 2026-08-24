from .base import *  # noqa: F403

DEBUG = env.bool("DJANGO_DEBUG", default=True)  # noqa: F405

REST_FRAMEWORK["DEFAULT_RENDERER_CLASSES"] += [  # noqa: F405
    "rest_framework.renderers.BrowsableAPIRenderer",
]
