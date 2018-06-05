import sqlite3

from sqlite3 import OperationalError

from ormik import ModelRegistrationError
from ormik.models import Model
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

    def register_models(self, models_to_register=None):
        if models_to_register is None:
            models_to_register = []
        elif not isinstance(models_to_register, list):
            models_to_register = [models_to_register]

        for model in models_to_register:
            if not issubclass(model, Model):
                raise ModelRegistrationError(
                    f'Please pass list of models to {self}.'
                    f'"{model}" is not a Model'
                )
            model.query_manager = QueryManager(self, model)
