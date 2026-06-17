# -*- coding: utf-8 -*-
"""
    This is general utilities for this project
"""


def documenting_parameter(*sub):
    """
        This method only replace a value of another functions
         docstring.
    :param sub:
    :return:
    """
    def dec(obj):
        """

        :param obj:
        :return:
        """
        obj.__doc__ = obj.__doc__.format(*sub)
        return obj
    return dec
