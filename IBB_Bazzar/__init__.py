"""Correctif Django 5.1 + Python 3.14 : copie de BaseContext dans l'admin."""
from copy import copy as copy_fn

from django.template.context import BaseContext


def _copy_base_context(self):
    duplicate = BaseContext()
    duplicate.__class__ = self.__class__
    duplicate.__dict__ = copy_fn(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


BaseContext.__copy__ = _copy_base_context
