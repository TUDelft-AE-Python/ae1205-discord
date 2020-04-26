# Discord educational bot for the Aerospace Engineering Python course
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

import os
from pathlib import Path

import pytest

from edubot.bot import EduBot
from tests.helpers import MockMember, MockUser


@pytest.fixture(scope="module")
def edubot() -> EduBot:
    """Returns an instantiated edubot."""
    return EduBot()


def test_command_prefix(edubot):
    """Ensures command_prefix of EduBot is not changed unexpectedly."""
    assert edubot.command_prefix == "!"


def test_mkdir(edubot, tmp_path, monkeypatch):
    """Checking if datadir is correctly instantiated."""
    assert edubot.datadir is not None
    assert os.path.exists(edubot.datadir)

    # Monkeypatching Path.home() to force creation of a new dir
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    test_bot = edubot.__class__()  # Creating a new instance of EduBot
    assert str(test_bot.datadir) == str(tmp_path / ".edubot")


@pytest.mark.asyncio
async def test_on_ready(edubot, capture_print):
    """Checking if the correct print statement is isued `on_ready`."""
    await edubot.on_ready()
    assert capture_print.statement == "None has connected to Discord!"


TEST_DM_TEST_CASES = {
    "argnames": "member",
    "argvalues": [MockUser(name="Uncle"), MockMember(name="Bob")],
}


@pytest.mark.parametrize(**TEST_DM_TEST_CASES)
@pytest.mark.asyncio
async def test_dm_with_qualified_user(
    edubot, member, capture_print,
):
    """Testing if direct messaging works on discord objects."""
    # Testing with dm_channel already existing
    await edubot.dm(member, f"Hello {member.name}. This is Pytest!")


@pytest.mark.asyncio
async def test_dm_with_string_user(edubot, capture_print, monkeypatch):
    """Testing if direct messaging works when using string input."""
    # Adding a mock-member to EduBot to helps us test user retrieval
    member = MockMember(name="Uncle Bob")
    monkeypatch.setattr(edubot._connection, "_users", {"test": member})

    # Checking if the conditional statement functions and that it was
    # able to retrieve the correct-member
    await edubot.dm("Test", f"Hello {member.name}. This is Pytest!")
