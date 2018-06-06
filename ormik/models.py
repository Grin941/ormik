from ormik import PkCountError, ModelRegistrationError, fields

__all__ = ['Model']


class ModelMeta(type):

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
            isinstance(attr, fields.Field)
        }
        model_cls._table = clsdict.get('__tablename__', name.lower())
        model_cls._pk = None

        pk_count = 0
        for model_field_name, model_field in model_cls._fields.items():
            model_field.name = model_field_name
            model_cls._fields[model_field_name] = model_field
            if model_field.is_primary_key:
                if pk_count > 0:
                    # PK is already set
                    raise PkCountError(
                        f'Model "{model_cls.__name__}" has >1 PKs.'
                    )

                model_cls._pk = model_field
                pk_count += 1

            # Create reverse_attr for FK model
            if isinstance(model_field, fields.ForeignKeyField):
                setattr(
                    model_field.rel_model,
                    model_field.reverse_name,
                    fields.ReversedForeignKeyField(model_cls, model_field.name)
                )

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
        if self._pk is None and self.__class__ is not Model:
            raise PkCountError(
                f'Model "{self.__class__.__name__}" has no PKs.'
            )

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
