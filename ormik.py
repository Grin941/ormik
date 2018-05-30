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


class ReversedForeignKeyField:

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

    def __new__(mtcls, name, bases, clsdict):
        model_fields, model_table = {
            key: val for key, val in clsdict.items() if
            isinstance(val, Field)
        }, name.lower()

        # Add bases fields to model_cls
        for base_class in bases:
            if not type(base_class) == ModelMeta: continue

            for field_name, field in base_class._fields.items():
                model_fields[field_name] = field
                clsdict[field_name] = field

        # Create model_cls
        model_cls = super().__new__(mtcls, name, bases, clsdict)
        model_cls._fields = model_fields
        model_cls._table = clsdict.get('__tablename__', model_table)

        pk_count = 0
        for model_field_name in model_fields:
            model_field = clsdict[model_field_name]
            model_field.name = model_field_name
            if model_field.is_primary_key:
                pk_count += 1

            # Create reverse_attr for FK model
            if isinstance(model_field, ForeignKeyField):
                setattr(
                    model_field.rel_model,
                    model_field.reverse_name,
                    ReversedForeignKeyField(model_cls, model_field.name)
                )

        if pk_count > 2:
            # Only one PK may be defined
            raise ValueError(
                f'Model "{name}" has {pk_count - 1} PKs.'
            )
        elif pk_count == 2:
            # Model has user defined PK, so exclude default one
            model_fields.pop('_id')
            clsdict.pop('_id')

        return model_cls


class Model(metaclass=ModelMeta):

    _id = AutoField()

    def __init__(self, *args, **kwargs):
        for field_name, field in self.__class__._fields.items():
            field_value = kwargs.get(field_name, field.default_value)
            setattr(self, field_name, field_value)


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
