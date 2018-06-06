import pytest 

from ormik import fields, models, PkCountError


def test_model_fields_inherits_from_bases(BaseModel):

    class Model(BaseModel):
        query_manager = 'Mock'

    model = Model()
    assert model._fields == {
        'id': BaseModel._fields['id']
    }


def test_model_should_have_pk():

    class Model(models.Model):
        query_manager = 'Mock'

    with pytest.raises(PkCountError):
        model = Model()


def test_model_should_have_no_more_than_one_pk(BaseModel):

    with pytest.raises(PkCountError):
        class Model(BaseModel):
            query_manager = 'Mock'
            new_id = fields.IntegerField(primary_key=True)
