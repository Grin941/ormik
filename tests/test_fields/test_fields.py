import pytest

from ormik import fields, FieldError


class MockModel(object):
    """ Mock Model """

    _pk = fields.AutoField(name='id')

    @classmethod
    def get(*args, **kwargs):
        return MockModel()


def test_field_is_nullable_and_has_no_default_raise_error():
    field = fields.CharField(name='field', is_nullable=False, default=None)
    with pytest.raises(FieldError):
        field.__set__(MockModel(), None)

def test_sized_field_error():
    field = fields.CharField(name='sized', max_length=1)
    with pytest.raises(FieldError):
        field.__set__(MockModel(), 'wqe')


def test_typed_field_error():
    field = fields.CharField(name='str_field')
    with pytest.raises(FieldError):
        field.__set__(MockModel(), 1)


def test_fk_value_should_be_related_model_instance_None_or_int():
    field = fields.ForeignKeyField(name='fk', model=MockModel, reverse_name='fields')
    field.__set__(MockModel(), None)  # No error
    field.__set__(MockModel(), 1)  # No error
    field.__set__(MockModel(), MockModel())  # No error
    with pytest.raises(FieldError):
        field.__set__(MockModel(), 'char_for_example')
