import sqlite3


CASCADE = 'CASCADE'
RESTRICT = 'RESTRICT'
SET_NULL = 'SET_NULL'
NO_ACTION = 'NO ACTION'


class FieldSQL:

    SQL_TYPES_MAPPING = {
        str: 'VARCHAR',
        int: 'INTEGER',
        bool: 'BOOLEAN',
    }

    def __init__(self, field, *args, **kwargs):
        self.field = field

    def _generate_field_sql(self):
        field = self.field
        field_type = int if not hasattr(field, 'ty') else field.ty
        field_is_autoincremented = isinstance(field, AutoField)
        sql = f'{field.name} {self.SQL_TYPES_MAPPING[field_type]}'

        if hasattr(field, 'max_length'):
            sql += f'({field.max_length})'

        if field.is_primary_key:
            sql += f' PRIMARY KEY'

        if not (field.is_nullable or field_is_autoincremented):
            sql += f' NOT NULL'

        if field.default_value is not None:
            sql += f' DEFAULT {field.default_value}'

        if field_is_autoincremented:
            sql += f' AUTOINCREMENT'

        return sql

    def _generate_fk_constraints(self):
        field = self.field
        return (
            f' FOREIGN KEY ({field.name})'
            f' REFERENCES {field.rel_model._table} ({field.name})'
            f' ON DELETE {field.on_delete} ON UPDATE {field.on_update}'
        ) if isinstance(field, ForeignKeyField) else None

    @property
    def column_definition(self):
        return self._generate_field_sql()

    @property
    def table_constraints(self):
        return self._generate_fk_constraints()


class Field:

    def __init__(
        self,
        name=None, null=True, default=None, primary_key=False,
        **kwargs
    ):
        self.name = name
        self.is_nullable = null
        self.default_value = default
        self.is_primary_key = primary_key
        self.query = FieldSQL(self)

    def __set__(self, instance, value):
        if not self.is_nullable and self.default_value is None:
            raise ValueError(
                f'Set default value for not nullable field "{self.name}"'
            )
        value = value or self.default_value
        instance.__dict__[self.name] = value

    def __repr__(self):
        return (
            f'{self.__class__.__name__}'
            f'({self.name}, pk={self.is_primary_key}, '
            f'null={self.is_nullable}, default={self.default_value})'
        )


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

    def __set__(self, instance, value=None):
        if value is None: value = self.rel_model()
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
        qs = cls.query_manager.get_queryset()
        if hasattr(qs, attr):
            def wrapper(*args, **kwargs):
                return getattr(qs, attr)(*args, **kwargs)
            return wrapper
        raise AttributeError(attr)


class QuerySQL:

    PRIMARY_MODEL_KEY = 'PRIMARYMODELKEY'

    FIELD_LOOKUP_MAPPING = {
        'exact': '=',
        'gt': '>',
        'gte': '>=',
        'lt': '<',
        'lte': '<=',
        'contains': 'LIKE',
        'in': 'IN',
        'is': 'IS',
    }

    def __init__(self, model, *args, **kwargs):
        self.model = model
        self.query_statements = {}
        self.fk_joins = {
            self.PRIMARY_MODEL_KEY: 't0'
        }
        self.model_instance = None

    @property
    def should_be_joined(self):
        return len(self.fk_joins) > 1

    @property
    def create_table_stmt(self):
        columns_definition_list, table_constraints_list = [], []
        for field in self.model._fields.values():
            columns_definition_list.append(
                field.query.column_definition
            )
            table_constraints = field.query.table_constraints
            if table_constraints is not None:
                table_constraints_list.append(table_constraints)
        columns_definition_sql = ', '.join(columns_definition_list)
        table_constraints_sql = ', '.join(table_constraints_list)
        if table_constraints_sql:
            columns_definition_sql = f'{columns_definition_sql},'

        return (
            f'CREATE TABLE IF NOT EXISTS {self.model._table} ('
            f'{columns_definition_sql}'
            f'{table_constraints_sql}'
            f')'
        )

    @property
    def drop_table_stmt(self):
        return f'DROP TABLE {self.model._table}'

    @property
    def insert_stmt(self):
        inst = self.model_instance
        columns, values = [], []
        for field_name, field in inst.fields.items():
            if isinstance(field, AutoField): continue
            field_value = getattr(inst, field_name)
            if isinstance(field, ForeignKeyField):
                field_value = field_value.id
            if field_value is None:
                field_value = 'NULL'

            columns.append(field_name)
            values.append(field_value)

        return (
            f'INSERT INTO {self.model._table}{tuple(columns)} '
            f'VALUES {tuple(values)}'
        )

    @property
    def select_stmt(self):
        sql_select_statement = self._sql_select_statement()
        sql_from_statement = self._sql_from_statement()
        sql_where_statement = self._sql_where_statement()

        return (
            f'SELECT {sql_select_statement} '
            f'FROM {sql_from_statement} '
            f'WHERE {sql_where_statement}'
        )

    @property
    def delete_stmt(self):
        if self.should_be_joined:
            sql_where_statement = (
                f'{self.model._pk.name} IN ({self.select_stmt})'
            )
        else:
            sql_where_statement = self._sql_where_statement(
                split_table_alias=True
            )

        return (
            f'DELETE FROM {self.model._table} '
            f'WHERE {sql_where_statement}'
        )

    @property
    def update_stmt(self):
        if self.should_be_joined:
            raise ValueError(
                'QuerySet can only update columns in the model’s main table'
            )
        sql_update_statement = self._sql_update_statement()
        sql_where_statement = self._sql_where_statement(split_table_alias=True)

        sql = (
            f'UPDATE {self.model._table} '
            f'SET {sql_update_statement}'
        )

        if sql_where_statement:
            sql += f' WHERE {sql_where_statement}'

        return sql

    def _sql_update_statement(self):
        sql_update_statement = []
        for field, (
            _, value
        ) in self.query_statements['UPDATE']['lookups'].items():
            table_alias, field_name = field.split('.')
            value = self._normalize_update_value(value)
            sql_update_statement.append(f'{field_name} = {value}')
        return ', '.join(sql_update_statement)

    def _sql_select_statement(self):
        select_fields = self.query_statements['SELECT']['fields']
        sql_select_statement = ', '.join(
            select_fields
        ) if select_fields else ', '.join(
            [f'{alias}.*' for alias in self.fk_joins.values()]
        )
        return sql_select_statement

    def _sql_from_statement(self):
        sql_from_statement = (
            f'{self.model._table} '
            f'AS {self.fk_joins.pop(self.PRIMARY_MODEL_KEY)}'
        )
        for field, table_alias in self.fk_joins.items():
            sql_from_statement += (
                f' LEFT JOIN {self.model._fields[field].rel_model._table} '
                f'AS {table_alias} '
                f'ON t0.{field} = '
                f'{table_alias}.{self.model._fields[field].rel_model._pk.name}'
            )
        return sql_from_statement

    def _sql_where_statement(self, split_table_alias=False):
        sql_where_statement = []
        for field_name, (
            lookup_statement, lookup_value
        ) in self.query_statements['WHERE']['lookups'].items():
            if split_table_alias:
                table_alias, field_name = field_name.split('.')
            lookup_value = self._normalize_lookup_value(
                lookup_statement, lookup_value
            )
            sql_where_statement.append(
                f'{field_name} {lookup_statement} {lookup_value}'
            )
        return ' AND '.join(sql_where_statement)

    def _normalize_lookup_value(self, lookup_statement, lookup_value):
        if lookup_statement == 'LIKE':
            lookup_value = f"'%{lookup_value}%'"
        elif lookup_statement == 'IN':
            lookup_value = f'{tuple(lookup_value)}'
        else:
            if isinstance(lookup_value, str):
                lookup_value = f"'{lookup_value}'"

        return lookup_value

    def _normalize_update_value(self, update_value):
        if isinstance(update_value, str):
            update_value = f"'{update_value}'"
        elif isinstance(update_value, Model):
            update_value = getattr(update_value, update_value._pk.name)
        if update_value is None:
            update_value = 'NULL'
        return update_value

    def _fill_statement_fields(self, statement_fields, *args):
        fk_joins = self.fk_joins
        for field_name in args:
            fk = self.PRIMARY_MODEL_KEY
            if '__' in field_name:
                # Field name is FK
                fk, field_name = field_name.split('__')
                if fk not in fk_joins:
                    fk_joins[fk] = f't{len(fk_joins)}'
            statement_fields.append(f'{fk_joins[fk]}.{field_name}')

    def _fill_statement_lookups(self, statement_lookups, **kwargs):
        fk_joins = self.fk_joins
        for field_lookup, lookup_value in kwargs.items():
            fk = self.PRIMARY_MODEL_KEY
            field_lookup_bricks = field_lookup.split('__')
            if field_lookup_bricks[-1] not in self.FIELD_LOOKUP_MAPPING:
                field_lookup_bricks.append('exact')

            if len(field_lookup_bricks) > 2:
                # Field is FK
                fk = field_lookup_bricks.pop(0)

            field_name, lookup_statement = field_lookup_bricks
            if fk not in fk_joins:
                fk_joins[fk] = f't{len(fk_joins)}'

            statement_lookups[
                f'{fk_joins[fk]}.{field_name}'
            ] = (
                f'{self.FIELD_LOOKUP_MAPPING[lookup_statement]}', lookup_value
            )

    def append_statement(self, statement_alias, *args, **kwargs):
        query_statement_dict = self.query_statements
        statement_meta = {
            'fields': [],
            'lookups': {}
        } if statement_alias not in query_statement_dict else \
            query_statement_dict[statement_alias]

        self._fill_statement_fields(statement_meta['fields'], *args)
        self._fill_statement_lookups(statement_meta['lookups'], **kwargs)

        query_statement_dict[statement_alias] = statement_meta

    def set_model_instance(self, model_instance=None, **kwargs):
        self.model_instance = self.model(**kwargs) if \
            model_instance is None else model_instance


class QuerySet():

    def __init__(self, query_manager, *args, **kwargs):
        self.query = QuerySQL(query_manager.model)
        self.model_pk_name = query_manager.model._pk.name
        self.db = query_manager.db

    def save(self, model_instance, *args, **kwargs):
        self.query.set_model_instance(model_instance, **kwargs)

        # TODO: write save()

    def create(self, *args, **kwargs):
        self.query.set_model_instance(**kwargs)

        return self._execute('insert_stmt')

    def update(self, *args, **kwargs):
        self.query.append_statement('UPDATE', *args, **kwargs)

        return self._execute('update_stmt')

    def delete(self):
        if self.query.should_be_joined:
            # Join should be made.
            # Make it upon 'pk' to create request "WHERE PK in (SELECT PK ...)
            self.query.append_statement(
                'SELECT', *(self.model_pk_name, ), **{}
            )

        return self._execute('delete_stmt')

    def values_list(self, *args, **kwargs):
        self.query.append_statement('SELECT', *args, **kwargs)

        return self._execute('select_stmt')

    def filter(self, *args, **kwargs):
        self.query.append_statement('WHERE', *args, **kwargs)

        return self

    def create_table(self, *args, **kwargs):
        self._execute('create_table_stmt')

        return True

    def drop_table(self, *args, **kwargs):
        self._execute('drop_table_stmt')

        return True

    def _execute(self, query_attr, *args, **kwargs):
        c = self.db.connection.cursor()
        self.querystring = f'{getattr(self.query, query_attr)};'
        print(self.querystring)
        c.execute(self.querystring)
        self.db.connection.commit()
        result = c.fetchall()
        print(result)


class QueryManager:

    def __init__(self, db, model):
        self.db, self.model = db, model

    def get_queryset(self):
        return QuerySet(self)


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

    def save(self, *args, **kwargs):
        self.__class__.save(self, *args, **kwargs)


class SqliteDatabase:

    def __init__(self, database):
        self.connection = self._connect(database)

    def _connect(self, database):
        conn = sqlite3.connect(
            database
        )
        # conn.isolation_level = None
        # conn.autocommit(True)
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
        author = ForeignKeyField(Author, 'books', is_nullable=True)
        title = CharField(default='Title')
        pages = IntegerField(default=100)
        coauthor = ForeignKeyField(Author, 'cobooks', is_nullable=True)
        rating = IntegerField(default=10)

    db = SqliteDatabase('tmp.db')
    db.register_models([Author, Book])

    author = Author(name='William Gibson')
    book = Book(author=author, title='Title', pages=100)

    Author.create_table()
    Book.create_table()

    # book = Book.create(author=author, title='New', pages=80)
    book = Book.create(title='New', pages=80)
    updated_rows_num = Book.filter(pages=80).update(
        pages=100000, title='LOL!', author=author
    )

    # books = Book.values_list('title', 'pages', 'author__name')
    Book.filter(
        title='LOL!', author__name__contains='William Gibson'
    ).filter(pages__gt=10).values_list('coauthor__name', 'rating')

    Book.filter(pages=10000).delete()

    # Author.drop_table()
    # Book.drop_table()
