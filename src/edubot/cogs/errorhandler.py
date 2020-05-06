import traceback
import sys
from discord.ext import commands
import discord


class ErrorHandler(commands.Cog):
    ''' Error handler Cog.'''

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        ''' Parse the event triggered when an error is raised while invoking a command.
            ctx   : Context
            error : Exception
        '''

        if hasattr(ctx.command, 'on_error'):
            return

        # First clear the offending message
        try:
            await ctx.message.delete()
        except:
            pass

        # Then do something with the error
        error = getattr(error, 'original', error)

        if isinstance(error, (commands.CommandNotFound, commands.UserInputError, commands.BadArgument)):
            return await ctx.send(f'Command or argument not recognised! Did you make a typo <@{ctx.author.id}>?', delete_after=10)

        elif isinstance(error, commands.DisabledCommand):
            return await ctx.send(f'{ctx.command} has been disabled, <@{ctx.author.id}>.', delete_after=10)

        elif isinstance(error, commands.NoPrivateMessage):
            try:
                return await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
            except:
                pass

        print(f'Ignoring exception {type(error)} in command {ctx.command}', file=sys.stderr)
