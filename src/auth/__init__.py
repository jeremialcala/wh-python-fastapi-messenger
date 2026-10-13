# -*- coding: utf-8 -*-
"""
    Authentication of everything that is not the Meta webhook: a JWT signed by the client, inside a JWE encrypted
    to the gateway. The submodules are imported one by one on purpose: `client` and `gateway_keys` need neither
    the settings nor the database, so they also run outside the service.
"""
