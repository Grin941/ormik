name = 'ormik'

__all__ = [
    'FieldError', 'PkCountError',
    'QueryError', 'DbOperationError', 'ModelRegistrationError',
    'ObjectDoesNotExistError', 'MultipleObjectsError',
    'CASCADE', 'RESTRICT', 'SET_NULL', 'NO_ACTION', 'NULL'
]


class FieldError(Exception):
    """ Model field validation error """


class PkCountError(Exception):
    """ Raise when Model has <> 1 pk """


class QueryError(Exception):
    """ Errors while generating SQL string """


class ObjectDoesNotExistError(Exception):
    """ Model instance does not exist """


class MultipleObjectsError(Exception):
    """ Multiple Model instances returned when only one is acceptable """


class DbOperationError(Exception):
    """ DB driver OperationError """


class ModelRegistrationError(Exception):
    """  Error with Model registration """
