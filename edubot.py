import os
import discord
from discord.ext import commands
from cogs import Queue

class EduBot(commands.Bot):
    ''' Discord bot for educational purposes.
        This bot is developed for the 1st year Python course
        for Aerospace Engineering students at TU Delft.
        It can manage queues of students, that can be assigned to tutors
        and student assistants for feedback sessions in voice channels.
    '''

    def __init__(self):
        super().__init__(command_prefix='!')
        self.classrooms = dict()
        self.add_cog(Queue(self))

    async def on_ready(self):
        ''' Bot initialisation upon connecting to Discord. '''
        print(f'{self.user} has connected to Discord!')

    async def dm(self, user, message):
        ''' Send a direct message to a user. '''
        if not isinstance(user, (discord.User, discord.Member)):
            user = self.get_user(user)
        if user:
            if not user.dm_channel:
                await user.create_dm()
            await user.dm_channel.send(message)


if __name__ == '__main__':
    TOKEN = os.getenv('DISCORD_TOKEN')
    bot = EduBot()
    bot.run(TOKEN)
