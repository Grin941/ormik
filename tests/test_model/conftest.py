import pytest

from ormik import models, fields


@pytest.fixture(scope="module")
def BaseModel():
    class BaseModel(models.Model):
        id = fields.AutoField()

    return BaseModel


