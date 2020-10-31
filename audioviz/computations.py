from __future__ import annotations

import abc
import dataclasses
import typing as t

import numpy as np


def computation():
    return dataclasses.dataclass(frozen=True)


_T = t.TypeVar("_T")


class Computation(abc.ABC, t.Generic[_T]):
    __hash__ = None
    
    def __post_init__(self):
        self._set_is_reset(True)

    @abc.abstractmethod
    def _compute(self) -> _T:
        raise NotImplementedError

    def value(self) -> _T:
        if self._is_reset:
            self._set_value(self._compute())
            self._set_is_reset(False)
        return self._value

    def reset(self) -> None:
        self._set_is_reset(True)
        for field in dataclasses.fields(self):
            input_ = getattr(self, field.name)
            input_.reset()
    
    def _set_is_reset(self, value: bool) -> None:
        object.__setattr__(self, "_is_reset", value)
    
    def _set_value(self, value: _T) -> None:
        object.__setattr__(self, "_value", value)


@computation()
class Constant(Computation[_T]):
    constant: _T

    def _compute(self) -> _T:
        return self.constant

