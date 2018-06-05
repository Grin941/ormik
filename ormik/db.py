import sqlite3

from sqlite3 import OperationalError as OperationalError

from ormik import ModelRegistrationError
from ormik.models import ModelMeta
from ormik.queryset import QueryManager


__all__ = ['SqliteDatabase', 'OperationalError']


class SqliteDatabase:

    def __init__(self, database):
        self.connection = self._connect(database)

    def _connect(self, database):
        conn = sqlite3.connect(
            database
        )
        conn.row_factory = sqlite3.Row
        return conn

    def register_models(self, models=None):
        if models is None:
            models = []
        elif not isinstance(models, list):
            models = [models]

        for model in models:
            if not type(model) == ModelMeta:
                raise ModelRegistrationError(
                    f'Please pass list of models to {self}.'
                    f'"{model}" is not a Model'
                )
            model.query_manager = QueryManager(self, model)
