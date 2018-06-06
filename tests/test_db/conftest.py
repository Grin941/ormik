import pytest
import mock

from ormik import db, models, fields


@pytest.fixture(scope="module")
def database():
    db_cls = db.SqliteDatabase

    with mock.patch.object(
        db_cls, '_connect', lambda database, database_name: database_name
    ):
        yield db_cls('test.db')


@pytest.fixture(scope="module")
def model():
    class Model(models.Model):
        query_manager = 'Mock'
        id = fields.AutoField()

    return Model
