import pytest

from ormik import ModelRegistrationError


def test_models_registered_in_db_should_be_model_instances(
    database, model
):
    database.register_models([model])  # No error
    with pytest.raises(ModelRegistrationError):
        database.register_models(['No model'])
