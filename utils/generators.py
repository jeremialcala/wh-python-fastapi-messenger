import logging
from classes import Settings
from random import choice


settings = Settings()
log = logging.getLogger(settings.environment)
alpha_numeric = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't',
                 'u', 'v', 'w', 'x', 'y', 'z', 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def generate_code(size=32):
    key = ""
    for x in range(0, size):
        key += str(choice(alpha_numeric)).upper()
    return key

