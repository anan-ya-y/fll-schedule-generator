"""PyInstaller hook for this repository's local workflow module.

The community hooks package includes a hook for an unrelated third-party package
also named ``workflow``.  An empty local hook prevents that package-metadata hook
from being applied to the scheduler's own ``workflow.py`` module.
"""

