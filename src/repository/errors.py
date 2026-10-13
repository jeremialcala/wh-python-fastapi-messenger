# -*- coding: utf-8 -*-
from mongoengine.errors import NotUniqueError, OperationError
from pymongo.errors import DuplicateKeyError, PyMongoError


class NotFound(LookupError):
    """
        The object does not exist, or it belongs to another client. Callers cannot tell the two apart, and must
        not be able to: both are answered with a 404.
    """


class Conflict(Exception):
    """The change cannot be made as things stand: the name is taken, or a rule on the number of keys forbids it."""


def database_failed(error: BaseException) -> bool:
    """
        Whether an error is the database not doing its part: it does not answer, it refuses the credentials, a
        write does not go through. That is whatever its driver raises, and what the document layer makes of it
        when saving. A value that is already there is not one of them: trying again would find it there again.
    """
    return (isinstance(error, (PyMongoError, OperationError))
            and not isinstance(error, (DuplicateKeyError, NotUniqueError)))
