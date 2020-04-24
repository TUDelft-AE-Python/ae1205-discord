import discord
from discord.ext import commands


class Poll(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot