import collections


class Field:
    def __get__(self, obj, obj_type=None):
        return obj._data[self._name]

    def __set__(self, obj, value):
        obj._data[self._name] = value


class CharField(Field):
    def __set__(self, obj, value):
        if not isinstance(value, str):
            raise TypeError(obj, self._name, str, value)
        super().__set__(obj, value)


class Relation(Field):
    def __init__(self, rel_model_class, reverse_name):
        self._rel_model_class = rel_model_class
        self._reverse_name = reverse_name

    def __set__(self, obj, value):
        if not isinstance(value, self._rel_model_class):
            raise TypeError(obj, self._name, self._rel_model_class, value)
        super().__set__(obj, value)


class ReverseRelation:
    def __init__(self, origin_model, field_name):
        self._origin_model = origin_model,
        self._field_name = field_name

    def __get__(self, obj, obj_type=None):
        return self._origin_model.S.filter(self._field_name=obj)


class ModelMeta:
    def __new__(cls, name, bases, attrs):
        type_new = type(name, bases, attrs)
        for field_name, field in attrs.items():
            if isinstance(field, Relation):
                setattr(
                    field._rel_model_class,
                    self._reverse_name,
                    ReverseRelation(type_new, field_name)
                )
            else:
                field._name = field_name
        attrs['_data'] = collections.defaultdict(attrs.keys())
        return type_new


class Model(metaclass=ModelMeta):
    pass


class ValidatorMeta(type):
    def __call__(cls, **attrs):
        for attr_name, attr in attrs.items():
            if not isinstance(attr, getattr(cls, attr_name)):
                raise TypeError()
        return dict(**attrs)


class Validator(metaclass=ValidatorMeta):
    pass
