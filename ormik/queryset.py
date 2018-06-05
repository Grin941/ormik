from functools import wraps

from ormik import \
    DbOperationError, ObjectDoesNotExistError, MultipleObjectsError
from ormik.db import OperationalError
from ormik.sql import QuerySQL
from ormik.models import Model


def clear_lookup_statements(cls_method):
    @wraps(cls_method)
    def wrapper(qs, *args, **kwargs):
        # Prevent passing Model instance in lookup statements
        # For example update(fk_field=fk_instance)
        for k, v in kwargs.items():
            if isinstance(v, Model):
                kwargs[k] = getattr(v, v._pk.name)
        return cls_method(qs, *args, **kwargs)
    return wrapper


class QuerySet():

    def __init__(self, query_manager, *args, **kwargs):
        self.query = QuerySQL(query_manager.model)
        self.model_pk_name = query_manager.model._pk.name
        self.model = query_manager.model
        self.db = query_manager.db
        self.querystring = None

    def __repr__(self):
        return f'{self.__class__.__name__}({self.model.__name__})'

    def __iter__(self):
        return iter(self.select_all())

    def _save(self, model_instance):
        inst_dict = model_instance.__dict__
        inst_id = inst_dict.pop('id')
        if inst_id is None:
            return self.create(**inst_dict)
        else:
            return self._update_and_get(**inst_dict)

    @clear_lookup_statements
    def _update_and_get(self, **kwargs):
        self.query.append_statement('UPDATE', **kwargs)
        cursor = self._execute('update_stmt')
        self.db.connection.commit()

        return self.get(**{self.model_pk_name: cursor.lastrowid})

    @clear_lookup_statements
    def create(self, **kwargs):
        self.query.append_statement('INSERT', **kwargs)
        cursor = self._execute('insert_stmt')
        self.db.connection.commit()

        return self.get(**{self.model_pk_name: cursor.lastrowid})

    @clear_lookup_statements
    def update(self, **kwargs):
        self.query.append_statement('UPDATE', **kwargs)
        cursor = self._execute('update_stmt')
        self.db.connection.commit()

        return cursor.rowcount

    def delete(self):
        if self.query.should_be_joined:
            # Join should be made.
            # Make it upon 'pk' to create request "WHERE PK in (SELECT PK ...)
            self.query.append_statement(
                'SELECT', *(self.model_pk_name, )
            )
        cursor = self._execute('delete_stmt')
        self.db.connection.commit()

        return cursor.rowcount

    @clear_lookup_statements
    def get(self, **kwargs):
        self.query.append_statement('SELECT', **kwargs)
        self.query.append_statement('WHERE', **kwargs)
        cursor = self._execute('select_stmt')

        values = cursor.fetchall()
        values_len = len(values)

        if values_len == 0:
            raise ObjectDoesNotExistError(
                f'Does not exist {self.model(**kwargs)}'
            )
        elif values_len > 1:
            raise MultipleObjectsError(
                'Multiple objects error {self.model(**kwargs)}'
            )

        return self.model(**dict(values[0]))

    @clear_lookup_statements
    def get_or_create(self, **kwargs):
        try:
            return self.get(**kwargs)
        except ObjectDoesNotExistError:
            return self.create(**kwargs)

    def select_all(self):
        self.query.append_statement('SELECT')
        cursor = self._execute('select_stmt')
        values = cursor.fetchall()

        return [
            self.model(
                **dict(init_kwargs)
            ) for init_kwargs in values
        ]

    def values(self, *args):
        self.query.append_statement(
            'SELECT', with_fields_alias=True, *args
        )
        cursor = self._execute('select_stmt')

        return [
            dict(values_row) for values_row in cursor.fetchall()
        ]

    @clear_lookup_statements
    def filter(self, **kwargs):
        self.query.append_statement('WHERE', **kwargs)

        return self

    def create_table(self):
        self._execute('create_table_stmt')
        self.db.connection.commit()

        return True

    def drop_table(self):
        self._execute('drop_table_stmt')
        self.db.connection.commit()

        return True

    def _execute(self, query_attr):
        c = self.db.connection.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        self.querystring = f'{getattr(self.query, query_attr)};'
        try:
            c.execute(self.querystring)
        except OperationalError as e:
            raise DbOperationError(str(e), self.querystring)

        return c


class QueryManager:

    def __init__(self, db, model):
        self.db, self.model = db, model

    def get_queryset(self):
        return QuerySet(self)
