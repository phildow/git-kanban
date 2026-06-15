"""Top-level package exports and compatibility imports.

Test discovery imports package paths like ``kanban.services`` and
``kanban.storage`` directly. Some modules still use legacy absolute imports
(``from models import ...`` / ``from repository import ...``), so this module
imports those submodules eagerly and exposes compatibility aliases.
"""

from __future__ import annotations

import sys

from . import models as models
from . import repository as repository

# Compatibility for legacy absolute imports inside the package.
sys.modules.setdefault("models", models)
sys.modules.setdefault("repository", repository)

from . import services as services
from . import storage as storage

__all__ = ["models", "repository", "services", "storage"]
