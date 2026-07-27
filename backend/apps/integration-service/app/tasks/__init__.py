"""Celery task package.

Do not import task modules eagerly here.
Python imports package `app.tasks` before submodules; eager imports caused
integration-service and celery-worker startup failures when optional modules
had unresolved dependencies.
"""

__all__: list[str] = []
