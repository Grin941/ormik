import sqlite3
import queue


CASCADE = 'CASCADE'
RESTRICT = 'RESTRICT'
SET_NULL = 'SET_NULL'
NO_ACTION = 'NO ACTION'


class FieldSQL:

    SQL_TYPES_MAPPING = {
        str: 'CHAR',
        int: 'INTEGER',
        bool: 'BOOL',
    }

    def _generate_field_sql(self, field):
        field_type = int if not hasattr(field, 'ty') else field.ty
        field_is_autoincremented = isinstance(field, AutoField)
        sql = f'{field.name} {self.SQL_TYPES_MAPPING[field_type]}'

        if hasattr(field, 'max_length'):
            sql += f'({field.max_length})'

        if field.is_primary_key:
            sql += f' PRIMARY KEY'

        if field.is_nullable and not field_is_autoincremented:
            sql += f' NOT NULL'

        if field.default_value is not None:
            sql += f' DEFAULT {field.default_value}'

        if field_is_autoincremented:
            sql += f' AUTOINCREMENT'

        return sql

    def _generate_fk_constraints(self, field):
        return (
            f' FOREIGN KEY ({field.name})'
            f' REFERENCES {field.rel_model._table} ({field.name})'
            f' ON DELETE {field.on_delete} ON UPDATE {field.on_update}'
        )

    def __set__(self, field, value):
        self.field = field

    def __get__(self, field, field_type=None):
        return (
            f'{self._generate_field_sql(field)},'
            f'{self._generate_fk_constraints(field)}'
        ) if isinstance(field, ForeignKeyField) else \
            f'{self._generate_field_sql(field)}'


class Field:

    sql = FieldSQL()

    def __init__(
        self,
        name=None, null=True, default=None, primary_key=False,
        **kwargs
    ):
        self.name = name
        self.is_nullable = null
        self.default_value = default
        self.is_primary_key = primary_key
        self.sql = self

    def __set__(self, instance, value):
        if not self.is_nullable and self.default_value is None:
            raise ValueError(
                f'Set default value for not nullable field "{self.name}"'
            )
        value = value or self.default_value
        instance.__dict__[self.name] = value

    def __repr__(self):
        return f'{self.__class__.__name__}' \
               f'({self.name}, pk={self.is_primary_key}, ' \
               f'null={self.is_nullable}, default={self.default_value})'


class SizedField(Field):

    def __init__(self, *args, max_length=128, **kwargs):
        self.max_length = max_length
        super().__init__(*args, **kwargs)

    def __set__(self, instance, value):
        if value is not None and len(value) > self.max_length:
            raise ValueError(
                f'"{self.name}" field maxlen should be < {self.maxlen}'
            )
        super().__set__(instance, value)


class TypedField(Field):
    ty = object

    def __set__(self, instance, value):
        if not (isinstance(value, self.ty) or value is None):
            raise TypeError(
                f'Expected {self.ty} type for "{self.name}" Field'
            )
        super().__set__(instance, value)


class ForeignKeyField(Field):

    def __init__(
        self, model, reverse_name, *args,
        on_delete=NO_ACTION, on_update=NO_ACTION,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.rel_model = model
        self.reverse_name = reverse_name
        self.on_delete = on_delete
        self.on_update = on_update

    def __set__(self, instance, value):
        if not isinstance(value, self.rel_model):
            raise TypeError(instance, self.name, self.rel_model, value)
        super().__set__(instance, value)


class ReversedForeignKeyField(Field):

    def __init__(self, origin_model, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.origin_model = origin_model
        self.field_name = field_name

    def __get__(self, instance, instance_type=None):
        if instance is not None:
            return self.origin_model.filter(**{self.field_name: instance})
        return self


class CharField(TypedField, SizedField):
    ty = str


class BooleanField(TypedField):
    ty = bool


class IntegerField(TypedField):
    ty = int


class AutoField(IntegerField):

    def __init__(self, *args, **kwargs):
        if kwargs.get('primary_key') is False:
            raise ValueError(
                f'{self} should be the primary_key.'
            )
        kwargs['primary_key'] = True
        super().__init__(*args, **kwargs)


class ModelMeta(type):

    @staticmethod
    def _add_reversed_fk(fk_field, fk_model):
        setattr(
            fk_field.rel_model,
            fk_field.reverse_name,
            ReversedForeignKeyField(fk_model, fk_field.name)
        )

    @staticmethod
    def _validate_pk_count(pk_count, model_name):
        # 1 PK should be defined
        if pk_count != 1 and model_name != 'Model':
            raise ValueError(
                f'Model "{model_name}" has {pk_count} PKs.'
            )

    def __new__(mtcls, name, bases, clsdict):
        # Add bases fields to model_cls
        for base_class in bases:
            if not type(base_class) == ModelMeta: continue

            for field_name, field in base_class._fields.items():
                clsdict[field_name] = field

        # Create model_cls
        model_cls = super().__new__(mtcls, name, bases, clsdict)
        model_cls._fields = {
            attr_name: attr for attr_name, attr in
            model_cls.__dict__.items() if
            isinstance(attr, Field)
        }
        model_cls._table = clsdict.get('__tablename__', name.lower())
        model_cls._pk = None

        pk_count = 0
        for model_field_name, model_field in model_cls._fields.items():
            model_field.name = model_field_name
            if model_field.is_primary_key:
                model_cls._pk = model_field
                pk_count += 1

            # Create reverse_attr for FK model
            if isinstance(model_field, ForeignKeyField):
                ModelMeta._add_reversed_fk(model_field, model_cls)

        ModelMeta._validate_pk_count(pk_count, name)

        return model_cls

    def __getattr__(cls, attr):
        """ Make query upon Model class.
        Example: Model.create_table()
        """
        if hasattr(cls.query_manager, attr):
            def wrapper(*args, **kwargs):
                return getattr(cls.query_manager, attr)(*args, **kwargs)
            return wrapper
        raise AttributeError(attr)


PRIMARY_MODEL_KEY = 'PRIMARYMODELKEY'


class SqlStatementsQueue(queue.PriorityQueue):

    STATEMENT_ALIAS_PRIORITY = {
        'SELECT': 1,
        'UPDATE': 1,
        'INSERT': 1,
        'DELETE': 1,
        'CREATE': 1,
        'DROP': 1,
        'WHERE': 2,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.priority_statement_in_use = False
        self.priorities_in_use = set()

    def append(self, statement):
        sql_statement, statement_alias = statement
        statement_priority = self.STATEMENT_ALIAS_PRIORITY[statement_alias]
        if statement_priority == 1:
            self.priority_statement_in_use = True
            if statement_priority in self.priorities_in_use:
                # Swap priority statements
                self.queue.pop(0)
        self.priorities_in_use.add(statement_priority)
        self.put((statement_priority, sql_statement))

    @property
    def values(self):
        values = []
        while not self.empty():
            values.append(self.queue.pop(0)[1])
        return values


class QuerySet:

    def __init__(self, db, *args, **kwargs):
        self.db = db
        self.query = ''
        self._reset()

    def append_statement(self, sql_statement):
        statement_alias = sql_statement.split(None, 1)[0].strip()
        self.sql_statements_queue.append((sql_statement, statement_alias))

    def _reset(self):
        self.sql_statements_queue = SqlStatementsQueue()
        self.models_fields_to_select = {
            PRIMARY_MODEL_KEY: ('t0', [])
        }

    @property
    def priority_statement_in_use(self):
        return self.sql_statements_queue.priority_statement_in_use

    def add_field_to_select(self, field, fk_key=PRIMARY_MODEL_KEY):
        self.models_fields_to_select[fk_key][1].append(field)

    def add_table_alias_to_select(self, alias, fk_key):
        self.models_fields_to_select[fk_key] = (alias, [])

    def execute(self, *args, **kwargs):
        c = self.db.connection.cursor()
        self.query = f"{''.join(self.sql_statements_queue.values)};"
        print(self.query)
        c.execute(self.query)
        print(c.fetchone())
        self.db.connection.commit()
        self._reset()


FIELD_LOOKUP_MAPPING = {
    'exact': '=',
    'gt': '>',
    'gte': '>=',
    'lt': '<',
    'lte': '<=',
    'contains': 'LIKE',
    'in': 'IN',
}


class QueryManager:

    def __init__(self, db, model):
        self.model = model
        self.queryset = QuerySet(db)

    def _populate_models_fields_to_select(self, *args, **kwargs):
        tables_counter = 0
        if not args:
            args = [f'{PRIMARY_MODEL_KEY}__*']
            for field_name, field in self.model._fields.items():
                if isinstance(field, ForeignKeyField):
                    args.append(f'{field_name}__*')

        for field in args:
            fk, field_name = PRIMARY_MODEL_KEY, field
            if '__' in field:
                fk, field_name = field.split('__')

            if fk not in self.queryset.models_fields_to_select:
                tables_counter += 1
                self.queryset.add_table_alias_to_select(
                    f't{tables_counter}', fk_key=fk
                )

            self.queryset.add_field_to_select(field_name, fk_key=fk)

    def __get__(self, model, model_type=None):
        return self

    def create(self, *args, **kwargs):
        inst = self.model(**kwargs)
        columns, values = [], []
        for field_name, field in inst.fields.items():
            if isinstance(field, AutoField): continue
            field_value = getattr(inst, field_name)
            if isinstance(field, ForeignKeyField):
                field_value = field_value.id

            columns.append(field_name)
            values.append(field_value)

        sql = (
            f'INSERT INTO {self.model._table} {tuple(columns)} '
            f'VALUES {tuple(values)}'
        )
        self.queryset.append_statement(sql)

        return self.queryset.execute()

    def update(self, *args, **kwargs):
        update_statements = []
        for field_name, field_value in kwargs.items():
            if isinstance(field_value, Model):
                field_value = field_value.id
            if isinstance(field_value, str):
                field_value = f"'{field_value}'"

            update_statement = f"{field_name} = {field_value}"
            update_statements.append(update_statement)
        update_statements = ', '.join(update_statements)

        sql = (
            f'UPDATE {self.model._table} '
            f'SET {update_statements}'
        )
        self.queryset.append_statement(sql)

        return self.queryset.execute()

    def delete(self):
        primary_table_alias = \
            self.queryset.models_fields_to_select[PRIMARY_MODEL_KEY][0]
        sql = f'DELETE FROM {self.model._table} AS {primary_table_alias}'
        self.queryset.append_statement(sql)

        return self.queryset.execute()

    def values_list(self, *args, **kwargs):
        self._select(*args)

        return self.queryset.execute()

    def _select(self, *args, **kwargs):
        self._populate_models_fields_to_select(*args)

        sql_fields_statement = []
        sql_from_statement = {}
        for fk, (
            table_alias, table_fields_list
        ) in self.queryset.models_fields_to_select.items():
            # Fill FROM tables
            table_name, field = (
                self.model._table,
                self.model._fields.get(fk, fk)
            )
            if isinstance(field, ForeignKeyField):
                sql_from_statement[field.name] = (
                    f'LEFT JOIN {field.rel_model._table} AS {table_alias} '
                    f'ON t0.{field.name} = '
                    f'{table_alias}.{field.rel_model._pk.name}'
                )
            else:
                sql_from_statement[field] = f'{table_name} AS {table_alias}'

            # Fill SELECT fields
            for table_field in table_fields_list:
                sql_fields_statement.append(f'{table_alias}.{table_field}')

        sql_fields_statement = ', '.join(sql_fields_statement)
        sql_from_statement = ' '.join(sql_from_statement.values())

        sql = (
            f'SELECT {sql_fields_statement} '
            f'FROM {sql_from_statement}'
        )
        self.queryset.append_statement(sql)

    def filter(self, *args, **kwargs):
        if not self.queryset.priority_statement_in_use:
            self._select(*args, **kwargs)

        where_statement_clauses = []
        for field_lookup, lookup_value in kwargs.items():
            field_lookup_bricks = field_lookup.split('__')
            if field_lookup_bricks[-1] not in FIELD_LOOKUP_MAPPING:
                field_lookup_bricks.append('exact')
            field = field_lookup_bricks.pop(0)

            # Get field = {table_alias}.{field_name}
            if len(field_lookup_bricks) > 1:
                # Field is FK
                fk_table_alias = \
                    self.queryset.models_fields_to_select[field][0]
                fk_table_field = field_lookup_bricks.pop(0)
                field = f'{fk_table_alias}.{fk_table_field}'
            else:
                primary_table_alias = \
                    self.queryset.models_fields_to_select[PRIMARY_MODEL_KEY][0]
                field = f'{primary_table_alias}.{field}'

            # Get value with regard to lookup statement
            lookup_statement = FIELD_LOOKUP_MAPPING[field_lookup_bricks.pop()]
            if lookup_statement == 'LIKE':
                lookup_value = f"'%{lookup_value}%'"
            elif lookup_statement == 'IN':
                lookup_value = f'{tuple(lookup_value)}'
            else:
                if isinstance(lookup_value, str):
                    lookup_value = f"'{lookup_value}'"

            where_statement_clauses.append(
                f'{field} {lookup_statement} {lookup_value}'
            )

        where_statement_clauses = ' AND '.join(where_statement_clauses)
        sql = f' WHERE {where_statement_clauses}'
        self.queryset.append_statement(sql)

        return self

    def create_table(self, *args, **kwargs):
        fields_declaration = ', '.join([
            field.sql for field in self.model._fields.values()
        ])

        sql = (
            f'CREATE TABLE IF NOT EXISTS {self.model._table} ('
            f'{fields_declaration}'
            f')'
        )
        self.queryset.append_statement(sql)
        self.queryset.execute()

        return True

    def drop_table(self, *args, **kwargs):
        sql = f'DROP TABLE {self.model._table}'
        self.queryset.append_statement(sql)
        self.queryset.execute()

        return True


class Model(metaclass=ModelMeta):

    def __init__(self, *args, **kwargs):
        if self.query_manager is None:
            # query_manager attribute is set to a model
            # when register in database,
            # e.g. db.register_models(Model)
            raise ValueError(
                f'Please, register model '
                f'"{self.__class__.__name__}" to database.'
            )
        for field_name, field in self.fields.items():
            field_value = kwargs.get(field_name, field.default_value)
            setattr(self, field_name, field_value)

    @property
    def fields(self):
        return self.__class__._fields


class SqliteDatabase:

    def __init__(self, database):
        self.connection = self._connect(database)

    def _connect(self, database):
        conn = sqlite3.connect(
            database
        )
        conn.isolation_level = None
        return conn

    def register_models(self, models=None):
        if models is None:
            models = []
        elif not isinstance(models, list):
            models = [models]

        for model in models:
            if not type(model) == ModelMeta:
                raise ValueError(
                    f'Please pass list of models to {self}.'
                    f'"{model}" is not a Model'
                )
            model.query_manager = QueryManager(self, model)


if __name__ == '__main__':
    class Author(Model):

        id = AutoField()
        name = CharField()

    class Book(Model):

        id = AutoField()
        author = ForeignKeyField(Author, 'books')
        title = CharField()
        pages = IntegerField()

    db = SqliteDatabase('tmp.db')
    db.register_models([Author, Book])

    # author = Author(name='William Gibson')
    # book = Book(author=author, title='Title', pages=100)

    Author.create_table()
    Book.create_table()

    # book = Book.create(author=author, title='New', pages=80)
    # updated_rows_num = Book.filter(pages=80).update(
    #     pages=100000, title='LOL!', author=author
    # )

    # books = Book.values_list('title', 'pages', 'author__name')
    # books = Book.filter(
    #     title='LOL!', author__name__contains='William Gibson', pages__gt=10
    # )

    # # TODO: FK in delete!
    # deleted_rows_count = Book.filter(pages=10000).delete()

    # Author.drop_table()
    # Book.drop_table()
