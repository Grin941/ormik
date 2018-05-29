class Field:

    def __init__(self, name=None, **kwargs):
        self.name = name

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value


class SizedField(Field):

    def __init__(self, *args, maxlen=128, **kwargs):
        self.maxlen = maxlen
        super().__init__(*args, **kwargs)

    def __set__(self, instance, value):
        if len(value) > self.maxlen:
            raise ValueError(
                f'"{self.name}" field maxlen should be < {self.maxlen}'
            )
        super().__set__(instance, value)


class TypedField(Field):
    ty = object

    def __set__(self, instance, value):
        if not isinstance(value, self.ty):
            raise TypeError(
                f'Expected {self.ty} type for "{self.name}" Field'
            )
        super().__set__(instance, value)


class NullableField(Field):

    def __init__(self, *args, nullable=True, **kwargs):
        self.nullable = True
        super().__init__(*args, **kwargs)


class CharField(TypedField, SizedField, NullableField):
    ty = str


class IntegerField(TypedField, NullableField):
    ty = int


class ModelMeta(type):

    def __new__(mtcls, name, bases, clsdict):
        fields_name = [
            key for key, val in clsdict.items() if
            isinstance(val, Field)
        ]

        for field_name in fields_name:
            clsdict[field_name].name = field_name

        model_cls = super().__new__(mtcls, name, bases, clsdict)
        model_cls._fields = fields_name

        return model_cls


class Model(metaclass=ModelMeta):

    def __init__(self, *args, **kwargs):
        for field_name, field_value in kwargs.items():
            if field_name in self.__class__._fields:
                setattr(self, field_name, field_value)


if __name__ == '__main__':
    class MyModel(Model):
        a = CharField()

    my_model = MyModel(a='123')
    print(my_model.a)
