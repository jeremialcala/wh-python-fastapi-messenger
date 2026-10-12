# -*- coding: utf-8 -*-


class NotFound(LookupError):
    """
        The object does not exist, or it belongs to another client. Callers cannot tell the two apart, and must
        not be able to: both are answered with a 404.
    """
