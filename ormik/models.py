from ormik import PkCountError, ModelRegistrationError
from ormik.fields import Field, ReversedForeignKeyField, ForeignKeyField

__all__ = ['Model']


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
            raise PkCountError(
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


class Model(metaclass=ModelMeta):

    def __init__(self, *args, **kwargs):
        if self.query_manager is None:
            # query_manager attribute is set to a model
            # when register in database,
            # e.g. db.register_models(Model)
            raise ModelRegistrationError(
                f'Please, register model '
                f'"{self.__class__.__name__}" to database.'
            )
        for field_name, field in self.fields.items():
            field_value = kwargs.get(field_name, field.default_value)
            setattr(self, field_name, field_value)

    def __repr__(self):
        fields_repr = ', '.join(
            [
                f'{field_name}={getattr(self, field_name)}'
                for field_name in self.fields.keys()
            ]
        )
        return (
            f'{self.__class__.__name__}({fields_repr}))'
        )

    @property
    def fields(self):
        return self.__class__._fields

    def save(self, *args, **kwargs):
        saved_inst = self.__class__._save(self, *args, **kwargs)
        self.__dict__ = saved_inst.__dict__
