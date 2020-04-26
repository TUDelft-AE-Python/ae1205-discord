# Discord bot for the TU Delft Aerospace Engineering Python course
# Copyright (C) 2020 Delft University of Technology

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public
# License along with this program.
# If not, see <https://www.gnu.org/licenses/>.


"""Contains config options, and custom markers/fixtures for pytest."""

import builtins
from dataclasses import dataclass, field
from typing import List

import pytest


@dataclass
class PrintCache:

    statements: List[str] = field(default_factory=list)

    @property
    def statement(self):  # noqa
        return self.statements[-1]

    def __call__(self, statement):  # noqa
        self.statements.append(statement)


@pytest.fixture(scope="function")
def capture_print(monkeypatch) -> PrintCache:
    """Capturs print statements from within the current test.

    All print statements:: can be accessed as follows:

        >>> capture_print.statements

    However, if only the latest print_statement as a :py:obj:`str` is
    desired the :py:attribute:`PrintCache.statement` property can be
    used::

        >>> capture_print.statement

    """
    p_cache = PrintCache()
    monkeypatch.setattr(builtins, "print", p_cache)
    return p_cache
