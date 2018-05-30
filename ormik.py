class Field:

    def __init__(
        self,
        name=None, null=False, default=None, primary_key=False,
        **kwargs
    ):
        self.name = name
        self.is_nullable = null
        self.default_value = default
        self.is_primary_key = primary_key

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value


class SizedField(Field):

    def __init__(self, *args, max_length=128, **kwargs):
        self.max_length = max_length
        super().__init__(*args, **kwargs)

    def __set__(self, instance, value):
        if len(value) > self.max_length:
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


class CharField(TypedField, SizedField):
    ty = str


class IntegerField(TypedField):
    ty = int


class ModelMeta(type):

    def __new__(mtcls, name, bases, clsdict):
        fields_name = {
            key for key, val in clsdict.items() if
            isinstance(val, Field)
        }

        for field_name in fields_name:
            clsdict[field_name].name = field_name

        model_cls = super().__new__(mtcls, name, bases, clsdict)
        model_cls._fields = clsdict

        return model_cls


class Model(metaclass=ModelMeta):

    def __init__(self, *args, **kwargs):
        for field_name, field in self.__class__._fields.values():
            field_value = kwargs.get(field_name, None)
            if field_name in kwargs:
                setattr(self, field_name, field_value)
            else:

        for field_name, field_value in kwargs.items():
            if field_name in self.__class__._fields:
                setattr(self, field_name, field_value)


if __name__ == '__main__':
    class MyModel(Model):
        a = CharField()

    my_model = MyModel(a='123')
    print(my_model.a, my_model.b)
