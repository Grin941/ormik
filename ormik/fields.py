from ormik import FieldError

from ormik.sql import FieldSQL, NO_ACTION, NULL

__all__ = [
    'CharField', 'IntegerField', 'BooleanField',
    'AutoField', 'ForeignKeyField'
]


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
            raise FieldError(
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
            raise FieldError(
                f'"{self.name}" field maxlen should be < {self.maxlen}'
            )
        super().__set__(instance, value)


class TypedField(Field):
    ty = object

    def __set__(self, instance, value):
        if not (isinstance(value, self.ty) or value is None):
            raise FieldError(
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
        if value in (NULL, None): value = self.rel_model()
        if isinstance(value, int):
            # Model instance pk was passed
            value = self.rel_model.get(**{
                self.rel_model._pk.name: value
            })
        if not isinstance(value, self.rel_model):
            raise FieldError(instance, self.name, self.rel_model, value)
        super().__set__(instance, value)


class ReversedForeignKeyField(Field):

    def __init__(self, origin_model, field_name, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.origin_model = origin_model
        self.field_name = field_name

    def __get__(self, instance, instance_type=None):
        if instance is not None:
            return self.origin_model.filter(**{
                self.field_name: getattr(instance, self.origin_model._pk.name)
            })
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
            raise FieldError(
                f'{self} should be the primary_key.'
            )
        kwargs['primary_key'] = True
        super().__init__(*args, **kwargs)
