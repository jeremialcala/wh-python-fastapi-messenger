from enum import Enum


class Role(Enum):
    CLIENT = "client"      # Owns chatbots and reaches only its own data
    OPERATOR = "operator"  # Runs the platform and registers clients
    SERVICE = "service"    # The response engine, for one client: reads what it needs to answer, writes nothing
