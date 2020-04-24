import discord
from discord.ext import commands


def getvoicechan(member):
    ''' Get member's voice channel. 
        Returns: The members voice channel, or None when not in a channel.
    '''
    return member.voice.channel if member and member.voice else None


class Queue:
    # Get reference to bot in a static
    bot = None
    # Keep queues in a static dict
    queues = dict()

    @classmethod
    async def qcheck(cls, ctx, qtype=None):
        queue = Queue.queues.get((ctx.guild.id, ctx.channel.id), None)
        if queue is None:
            ctx.send('This channel doesn\'t have a queue!')
            return False
        if isinstance(queue, qtype or cls):
            return True
        ctx.send(f'{ctx.invoked_with} is not a recognised command for the queue in this channel!')
        return False

    @staticmethod
    def makequeue(qid, qtype):
        if qid in Queue.queues:
            return 'This channel already has a queue!'
        else:
            # Get the correct subclass of Queue
            qclass = next(qclass for qclass in Queue.__subclasses__() if qclass.qtype == qtype)
            Queue.queues[qid] = qclass(qid)
            return f'Created a {qtype} queue'

    @staticmethod
    def addtoqueue(qid, *args):
        return Queue.queues[qid].add(*args)

    @staticmethod
    def load(qid):
        try:
            with open(f'{qid[0]}-{qid[1]}.csv', 'r') as fin:
                qtype = fin.readline()
                Queue.makequeue(qid, qtype)
                Queue.queues[qid].fromfile(fin)
                return f'Loaded a {qtype} queue for <#{qid[1]}> with {len(queue)} entries.'
        except IOError:
            return 'No saved queue available for this channel.'

    def __init__(self, qid):
        self.qid = qid
        self.queue = []

    def size(self):
        return len(self.queue)

    def add(self, *args):
        return ''

    def fromfile(self, fin):
        pass

    def tofile(self, fout):
        pass

    def save(self):
        with open(f'{self.qid[0]}-{self.qid[1]}.csv', 'w') as fout:
            fout.write(self.qtype)
            self.tofile(self, fout)

    async def takenext(self, ctx):
        pass

    async def putback(self, ctx):
        pass

    def whereis(self, uid):
        pass


class ReviewQueue(Queue):
    qtype = 'Review'

    def __init__(self, qid):
        super().__init__(qid)
        self.assigned = dict()

    def fromfile(self, fin):
        self.queue = [int(el) for el in fin.read().strip().split(',')]

    def tofile(self, fout):
        fout.write(','.join([str(el) for el in queue]))

    def add(self, member):
        try:
            pos = self.queue.index(member.id)
            return f'You are already in the queue <@{member.id}>! ' + \
                (f'There are still {pos} people waiting in front of you.' if pos else
                    'You are next in line!')
        except ValueError:
            self.queue.append(member.id)
            return f'Added <@{member.id}> to the queue at position {len(self.queue)}'
        self.queue.append(member)

    async def takenext(self, ctx):
        # Get the voice channel of the caller
        cv = getvoicechan(ctx.author)
        if cv is None:
            await ctx.send(f'<@{ctx.author.id}>: Please select a voice channel first where you want to interview the student!')
            return
        if not self.queue:
            await ctx.send(f'<@{ctx.author.id}>: Hurray, the queue is empty!')
            return

        # Get the next student in the queue
        count = len(self.queue)
        member = await ctx.guild.fetch_member(self.queue.pop(0))
        while count > 0 and not getvoicechan(member):
            count -= 1
            await self.bot.dm(member, f'You were invited by a TA, but you\'re not in a voice channel yet!'
                              'You will be placed back in the queue. Make sure that you\'re more prepared next time!')
            # Put the student back in the queue, and get the next one to try
            self.queue.insert(10, member.id)
            if count:
                member = await ctx.guild.fetch_member(self.queue.pop(0))
            else:
                await ctx.send(f'<@{ctx.author.id}> : There\'s noone in the queue who is ready (in a voice lounge)!')
                return

        # move the student to the callee's voice channel, and store him/her
        # as assigned for the caller
        self.assigned[ctx.author.id] = (
            member.id, self.qid, getvoicechan(member))
        await member.edit(voice_channel=cv)

        # are there still students in the queue?
        if self.queue:
            member = await ctx.guild.fetch_member(self.queue[0])
            await self.bot.dm(member,
                              f'Get ready! You\'re next in line for the queue in <#{ctx.channel.id}>!' +
                              ('' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!'))
            if len(self.queue) > 1:
                # Also send a message to the third person in the queue
                member = await ctx.guild.fetch_member(self.queue[1])
                await self.bot.dm(member,
                                  f'Almost there {member.name}, You\'re second in line for the queue in <#{ctx.channel.id}>!' +
                                  ('' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!'))

    async def putback(self, ctx):
        ''' Put the student you currently have in your voice channel back in the queue. '''
        uid, qid, voicechan = self.assigned.get(
            ctx.author.id, (False, False, False))
        if not uid:
            await ctx.send(f'<@{ctx.author.id}>: You don\'t have a student assigned to you yet!')
        else:
            self.queue.insert(10, uid)
            member = await ctx.guild.fetch_member(uid)
            await member.edit(voice_channel=voicechan)
            await self.bot.dm(member, 'You were moved back into the queue, probably because you didn\'t respond.')

    def whereis(self, uid):
        try:
            pos = self.queue.index(uid)
            return f'Hi <@{uid}>! ' + \
                (f'There are still {pos} people waiting in front of you.' if pos else
                 'You are next in line!')
        except ValueError:
            return f'You are not in the queue in this channel <@{uid}>!'


class QueueCog(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        Queue.bot = bot

    def cog_unload(self):
        # Save queues here
        return super().cog_unload()

    @commands.command()
    @commands.check(Queue.qcheck)
    @commands.has_permissions(administrator=True)
    async def takenext(self, ctx):
        """ Take the next in line from the queue. """
        qid = (ctx.guild.id, ctx.channel.id)
        await self.queues[qid].takenext(ctx)

    @commands.command()
    @commands.check(Queue.qcheck)
    @commands.has_permissions(administrator=True)
    async def putback(self, ctx):
        ''' Put the student you currently have in your voice channel back in the queue. '''
        qid = (ctx.guild.id, ctx.channel.id)
        await self.queues[qid].putback(ctx)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def makequeue(self, ctx, qtype='Review'):
        """ Make a queue in this channel. """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.send(Queue.makequeue(qid, qtype))

    @commands.command()
    @commands.check(Queue.qcheck)
    @commands.has_permissions(administrator=True)
    async def savequeue(self, ctx):
        Queue.queues[(ctx.guild.id, ctx.channel.id)].save()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def loadqueue(self, ctx):
        await ctx.send(Queue.load((ctx.guild.id, ctx.channel.id)))

    @commands.command(aliases=('ready', 'done'))
    @commands.check(lambda ctx: Queue.qcheck(ctx, ReviewQueue))
    async def queueme(self, ctx, *args):
        """ Add me to the queue in this channel """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.send(Queue.addtoqueue(qid, ctx.author))

    @commands.command()
    @commands.check(Queue.qcheck)
    async def whereami(self, ctx):
        """ What's my position in the queue of this channel. """
        uid = ctx.author.id
        await ctx.send(Queue.queues[(ctx.guild.id, ctx.channel.id)].whereis(uid))

    @commands.command()
    @commands.check(Queue.qcheck)
    @commands.has_permissions(administrator=True)
    async def queue(self, ctx, *, member: discord.Member = None):
        """ Admin command: check and add to the queue. """
        qid = (ctx.guild.id, ctx.channel.id)
        if member is None:
            # Only respond with the length of the queue
            size = Queue.queues[qid].size()
            await ctx.send(f'There are {size} entries in the queue of <#{ctx.channel.id}>')
        else:
            # Member is passed, add him/her to the queue
            await ctx.send(Queue.addtoqueue(qid, member))
