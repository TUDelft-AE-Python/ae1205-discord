import discord
from discord.ext import commands


def getvoicechan(member):
    ''' Get member's voice channel. 
        Returns: The members voice channel, or None when not in a channel.
    '''
    return member.voice.channel if member and member.voice else None


class Queue(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self._last_member = None
        self.queues = dict()

    def _add(self, qid, member):
        ''' Internal function to add someone to a queue. '''
        queue = self.queues.get(qid, None)
        if queue is None:
            return 'This channel doesn\'t have a queue!'
        else:
            print('ADD:', queue)
            try:
                pos = queue.index(member.id)
                return f'You are already in the queue <@{member.id}>! ' + \
                    (f'There are still {pos} people waiting in front of you.' if pos else
                     'You are next in line!')
            except ValueError:
                queue.append(member.id)
                return f'Added <@{member.id}> to the queue at position {len(queue)}'

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def takenext(self, ctx):
        """ Take the next in line from the queue. """
        queue = self.queues.get((ctx.guild.name, ctx.channel.id), None)
        if queue is None:
            await ctx.send('This channel doesn\'t have a queue!')
        else:
            # Get the voice channel of the callee
            cv = getvoicechan(ctx.author)
            if cv is None:
                await ctx.send(f'<@{ctx.author.id}>: Please select a voice channel first where you want to interview the student!')
                return
            if not queue:
                await ctx.send(f'<@{ctx.author.id}>: Hurray, the queue is empty!')
                return
            print(queue)
            # Get the next student in the queue
            count = len(queue)
            member = await ctx.guild.fetch_member(queue.pop(0))
            while count > 0 and not getvoicechan(member):
                count -= 1
                await self.bot.dm(member, f'You were invited by a TA, but you\'re not in a voice channel yet!' 
                             'You will be placed back in the queue. Make sure that you\'re more prepared next time!')
                # Put the student back in the queue, and get the next one to try
                queue.insert(10, member.id)
                if count:
                    member = await ctx.guild.fetch_member(queue.pop(0))
                else:
                    await ctx.send(f'<@{ctx.author.id}> : There\'s noone in the queue who is ready (in a voice lounge)!')
                    return

            # move the student to the callee's voice channel
            await member.edit(voice_channel=cv)
            # are there still students in the queue?
            if queue:
                member = await ctx.guild.fetch_member(queue[0])
                await self.bot.dm(member, 
                            f'Get ready! You\'re next in line for the queue in <#{ctx.channel.id}>!' +
                            ('' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!'))
                if len(queue) > 1:
                    # Also send a message to the third person in the queue
                    member = await ctx.guild.fetch_member(queue[1])
                    await self.bot.dm(member,
                        f'Almost there {member.name}, You\'re second in line for the queue in <#{ctx.channel.id}>!' +
                        ('' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!'))

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def makequeue(self, ctx):
        """ Make a queue in this channel. """
        qid = (ctx.guild.name, ctx.channel.id)
        if qid in self.queues:
            await ctx.send('This channel already has a queue!')
        else:
            self.queues[qid] = list()
            await ctx.send(f'Created a queue for channel <#{ctx.channel.id}>')

    @commands.command()
    async def queueme(self, ctx):
        """ Add me to the queue in this channel """
        qid = (ctx.guild.name, ctx.channel.id)
        await ctx.send(self._add(qid, ctx.author))

    @commands.command()
    async def whereami(self, ctx):
        """ What's my position in the queue of this channel. """
        uid = ctx.author.id
        queue = self.queues.get((ctx.guild.name, ctx.channel.id), None)
        if queue is None:
            await ctx.send('This channel doesn\'t have a queue!')
        else:
            try:
                pos = queue.index(uid)
                await ctx.send(f'Hi <@{uid}>! ' +
                               (f'There are still {pos} people waiting in front of you.' if pos else
                                'You are next in line!'))
            except ValueError:
                await ctx.send(f'You are not in the queue in this channel <@{uid}>!')

    @commands.command()
    async def queue(self, ctx, *, member: discord.Member = None):
        qid = (ctx.guild.name, ctx.channel.id)
        if member is None:
            # Only respond with the length of the queue
            queue = self.queues.get(qid, None)
            await ctx.send('This channel doesn\'t have a queue!' if queue is None else
                           f'There are {len(queue)} students in the queue of <#{ctx.channel.id}>')
        else:
            # Member is passed, add him/her to the queue
            await ctx.send(self._add(qid, member))
