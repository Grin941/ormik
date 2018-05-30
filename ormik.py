import sqlite3


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
        on_delete=None, on_update=None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.rel_model = model
        self.reverse_name = reverse_name

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
            # return self.origin_model.select().where(self.field_name=instance)
            return
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
        # No more than 1 PK should be defined
        if pk_count > 1:
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

        pk_count = 0
        for model_field_name, model_field in model_cls._fields.items():
            model_field.name = model_field_name
            if model_field.is_primary_key:
                pk_count += 1

            # Create reverse_attr for FK model
            if isinstance(model_field, ForeignKeyField):
                ModelMeta._add_reversed_fk(model_field, model_cls)

        ModelMeta._validate_pk_count(pk_count, name)

        return model_cls


class Model(metaclass=ModelMeta):

    def __init__(self, *args, connection=None, **kwargs):
        if connection is None:
            raise ValueError(
                f'Please, pass connection to work with a database.'
            )
        for field_name, field in self.__class__._fields.items():
            field_value = kwargs.get(field_name, field.default_value)
            setattr(self, field_name, field_value)


class _ConnectionState(object):
    def __init__(self, **kwargs):
        super(_ConnectionState, self).__init__(**kwargs)
        self.reset()

    def reset(self):
        self.closed = True
        self.conn = None
        self.transactions = []

    def set_connection(self, conn):
        self.conn = conn
        self.closed = False


class ExceptionWrapper(object):
    __slots__ = ('exceptions',)
    def __init__(self, exceptions):
        self.exceptions = exceptions
    def __enter__(self): pass
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            return
        if exc_type.__name__ in self.exceptions:
            new_type = self.exceptions[exc_type.__name__]
            exc_args = exc_value.args
            reraise(new_type, new_type(*exc_args), traceback)

EXCEPTIONS = {
    'ConstraintError': IntegrityError,
    'DatabaseError': DatabaseError,
    'DataError': DataError,
    'IntegrityError': IntegrityError,
    'InterfaceError': InterfaceError,
    'InternalError': InternalError,
    'NotSupportedError': NotSupportedError,
    'OperationalError': OperationalError,
    'ProgrammingError': ProgrammingError}

__exception_wrapper__ = ExceptionWrapper(EXCEPTIONS)


class SqliteDatabase:

    def __init__(self, database):
        self.database = database

    def _connect(self):
        conn = sqlite3.connect(
            self.database,
            timeout=self._timeout,
            **self.connect_params
        )
        conn.isolation_level = None
        try:
            self._add_conn_hooks(conn)
        except:
            conn.close()
            raise
        return conn

    def connect(self, reuse_if_open=False):
        with self._lock:
            if self.deferred:
                raise Exception('Error, database must be initialized before '
                                'opening a connection.')
            if not self._state.closed:
                if reuse_if_open:
                    return False
                raise OperationalError('Connection already opened.')

            self._state.reset()
            with __exception_wrapper__:
                self._state.set_connection(self._connect())
                self._initialize_connection(self._state.conn)
        return True

    def _initialize_connection(self, conn):
        pass


if __name__ == '__main__':
    class MyModel(Model):

        a = CharField()
        b = CharField(default='def')
        c = CharField()
        # d = CharField(null=False)
        # e = CharField(default=123)

    class Author(MyModel):
        __tablename__ = 'author_table'

        id = AutoField()
        num = IntegerField(default=0)
        status = CharField(default='new')
        name = CharField()

    class Book(Model):

        author = ForeignKeyField(Author, 'books')
        title = CharField()

    my_model = MyModel(a='123')
    author = Author(name='William Gibson')
    book = Book(author=author, title='Title')

    print(my_model._table, my_model._fields.keys())
    print(author._table, author._fields.keys())
    print(book.author.name, author.books)
