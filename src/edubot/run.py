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

"""Contains the :py:func:`cli` the entry-point of EduBot."""


import os

import click

from .bot import EduBot

TOKEN = os.getenv("DISCORD_TOKEN")


@click.command()
@click.option("--token", default=TOKEN, help="Specifies the Discord API Token")
def cli(token: str):
    """Command Line Interface (CLI) of :py:class:`Edubot`.

    Args:
        token: Discord API Token

    """
    assert token is not None, "No Discord API token could be retrieved"
    bot = EduBot()
    bot.run(token)
    return bot


if __name__ == "__main__":
    # Prevents gc (garbage-collection) of the bot
    bot = cli()
