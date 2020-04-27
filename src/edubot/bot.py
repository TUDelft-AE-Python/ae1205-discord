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

"""Contains the main :py:class:`EduBot` specification."""

import os
from pathlib import Path

import discord
from discord.ext import commands

from edubot.cogs import Poll, QueueCog


class EduBot(commands.Bot):
    """Discord bot for educational purposes.

    This bot is developed for the 1st year Python course for Aerospace
    Engineering students at TU Delft. It can manage queues of students,
    that can be assigned to tutors and student assistants for feedback
    sessions in voice channels.
    """

    def __init__(self):
        super().__init__(command_prefix="!", case_insensitive=True)
        self.classrooms = dict()
        self.datadir = Path.joinpath(Path.home(), ".edubot")
        if not Path.exists(self.datadir):
            Path.mkdir(self.datadir)
        self.add_cog(QueueCog(self))
        self.add_cog(Poll(self))

    async def on_ready(self):
        """Bot initialisation upon connecting to Discord."""
        print(f"{self.user} has connected to Discord!")

    async def dm(self, user, message):
        """Send a direct message to a user."""
        if not isinstance(user, (discord.User, discord.Member)):
            user = self.get_user(user)
        if user:
            if not user.dm_channel:
                await user.create_dm()
            await user.dm_channel.send(message)
