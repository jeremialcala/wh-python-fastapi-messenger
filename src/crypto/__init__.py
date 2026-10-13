# -*- coding: utf-8 -*-
"""
    Encryption of a client's data at rest. Each client has a data key; the fields that must not be readable from
    a copy of the database are encrypted with it. The data key itself is only ever stored wrapped by a master key
    that lives in the key service and never leaves it.
"""
