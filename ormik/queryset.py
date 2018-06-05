from ormik import \
    DbOperationError, ObjectDoesNotExistError, MultipleObjectsError
from ormik.db import OperationalError
from ormik.sql import QuerySQL


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

    def _save(self, model_instance, *args, **kwargs):
        inst_dict = model_instance.__dict__
        if inst_dict.get('id') is None:
            return self.create(*args, **inst_dict)
        else:
            return self._update_and_get(*args, **inst_dict)

    def _update_and_get(self, *args, **kwargs):
        self.query.append_statement('UPDATE', *args, **kwargs)
        cursor = self._execute('update_stmt')
        self.db.connection.commit()

        return self.get(**{self.model_pk_name: cursor.lastrowid})

    def create(self, *args, **kwargs):
        self.query.set_model_instance(**kwargs)
        cursor = self._execute('insert_stmt')
        self.db.connection.commit()

        return self.get(**{self.model_pk_name: cursor.lastrowid})

    def update(self, *args, **kwargs):
        self.query.append_statement('UPDATE', *args, **kwargs)
        cursor = self._execute('update_stmt')
        self.db.connection.commit()

        return cursor.rowcount

    def delete(self):
        if self.query.should_be_joined:
            # Join should be made.
            # Make it upon 'pk' to create request "WHERE PK in (SELECT PK ...)
            self.query.append_statement(
                'SELECT', *(self.model_pk_name, ), **{}
            )
        cursor = self._execute('delete_stmt')
        self.db.connection.commit()

        return cursor.rowcount

    def get(self, *args, **kwargs):
        self.query.append_statement('SELECT', *args, **kwargs)
        self.query.append_statement('WHERE', *args, **kwargs)
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

    def get_or_create(self, *args, **kwargs):
        try:
            return self.get(*args, **kwargs)
        except ObjectDoesNotExistError:
            return self.create(*args, **kwargs)

    def select_all(self, *args, **kwargs):
        self.query.append_statement('SELECT', *args, **kwargs)
        cursor = self._execute('select_stmt')
        values = cursor.fetchall()

        return [
            self.model(
                **dict(init_kwargs)
            ) for init_kwargs in values
        ]

    def values(self, *args, **kwargs):
        self.query.append_statement(
            'SELECT', with_fields_alias=True, *args, **kwargs
        )
        cursor = self._execute('select_stmt')

        return [
            dict(values_row) for values_row in cursor.fetchall()
        ]

    def filter(self, *args, **kwargs):
        self.query.append_statement('WHERE', *args, **kwargs)

        return self

    def create_table(self, *args, **kwargs):
        self._execute('create_table_stmt')
        self.db.connection.commit()

        return True

    def drop_table(self, *args, **kwargs):
        self._execute('drop_table_stmt')
        self.db.connection.commit()

        return True

    def _execute(self, query_attr, *args, **kwargs):
        c = self.db.connection.cursor()
        c.execute("PRAGMA foreign_keys = ON")
        self.querystring = f'{getattr(self.query, query_attr)};'
        try:
            c.execute(self.querystring)
        except OperationalError as e:
            print(self.querystring)
            raise DbOperationError(str(e))

        return c


class QueryManager:

    def __init__(self, db, model):
        self.db, self.model = db, model

    def get_queryset(self):
        return QuerySet(self)
