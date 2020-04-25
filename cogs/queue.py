import discord
from discord.ext import commands
from collections import OrderedDict


def getvoicechan(member):
    ''' Get member's voice channel. 
        Returns: The members voice channel, or None when not in a channel.
    '''
    return member.voice.channel if member and member.voice else None


class Queue:
    # Get reference to bot in a static
    bot = None
    datadir = None
    # Keep queues in a static dict
    queues = dict()

    @classmethod
    def saveall(cls):
        print('Saving all queues')
        for qid, queue in cls.queues.items():
            print('Saving queue', qid)
            queue.save()

    @classmethod
    def loadall(cls):
        msgs = []
        for qfile in cls.datadir.iterdir():
            qidstr = qfile.name.replace('.dat', '').split('-')
            qid = tuple(int(i) for i in qidstr)
            msgs.append(cls.load(qid))
        return '\n'.join(msgs)

    @classmethod
    async def qcheck(cls, ctx, qtype=''):
        queue = Queue.queues.get((ctx.guild.id, ctx.channel.id), None)
        if queue is None:
            await ctx.send('This channel doesn\'t have a queue!')
            return False
        if not qtype or qtype == queue.qtype:
            return True
        await ctx.send(f'{ctx.invoked_with} is not a recognised command for the queue in this channel!')
        return False

    @classmethod
    def makequeue(cls, qid, qtype):
        if qid in cls.queues:
            return 'This channel already has a queue!'
        else:
            # Get the correct subclass of Queue
            qclass = next(qclass for qclass in cls.__subclasses__() if qclass.qtype == qtype)
            cls.queues[qid] = qclass(qid)
            return f'Created a {qtype} queue'

    @classmethod
    def addtoqueue(cls, qid, *args):
        return cls.queues[qid].add(*args)

    @classmethod
    def load(cls, qid):
        try:
            fname = cls.datadir.joinpath(f'{qid[0]}-{qid[1]}.dat')
            with open(fname, 'r') as fin:
                qtype = fin.readline().strip()
                cls.makequeue(qid, qtype)
                cls.queues[qid].fromfile(fin)
                return f'Loaded a {qtype} queue for <#{qid[1]}> with {cls.queues[qid].size()} entries.'
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
        fname = Queue.datadir.joinpath(f'{self.qid[0]}-{self.qid[1]}.dat')
        print('Saving', fname)
        with open(fname, 'w') as fout:
            fout.write(self.qtype + '\n')
            self.tofile(fout)

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
        out = ','.join([str(el) for el in self.queue])
        fout.write(out)

    def add(self, member):
        try:
            pos = self.queue.index(member)
            return f'You are already in the queue <@{member}>! ' + \
                (f'There are still {pos} people waiting in front of you.' if pos else
                    'You are next in line!')
        except ValueError:
            self.queue.append(member)
            return f'Added <@{member}> to the queue at position {len(self.queue)}'
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


class QuestionQueue(Queue):
    qtype = 'Question'

    class Question:
        def __init__(self, askedby, qmsg):
            self.qmsg = qmsg
            self.followers = [askedby]

    def __init__(self, qid):
        super().__init__(qid)
        self.queue = OrderedDict()

    def fromfile(self, fin):
        data = [line.strip() for line in fin.readlines()]
        qmsgs, qfoll = data[::2], data[1::2]
        for idx, (qmsg, qf) in enumerate(zip(qmsgs, qfoll[:len(qmsgs)])):
            question = QuestionQueue.Question(0, qmsg)
            question.followers = [int(f) for f in qf.strip().split()]
            self.queue[idx+1] = question

    def tofile(self, fout):
        for qstn in self.queue.values():
            fout.write(qstn.qmsg + '\n')
            fout.write(' '.join([str(f) for f in qstn.followers]) + '\n')

    def follow(self, member, idx=None):
        """ Follow a question. """
        if not self.queue:
            return 'There are no questions in the queue!'
        if idx is None:
            msg = 'The following questions can be followed:\n'
            for qidx, qstn in self.queue.items():
                msg = msg + f'{qidx:02d}: {qstn.qmsg}' + \
                    ' (already following)\n' if member in qstn.followers else '\n'
            return msg

        question = self.queue.get(idx, None)
        if question is None:
            return f'No question in the queue with index {idx}'
        if member in question.followers:
            return f'You are already following question {idx} <@{member}>!'
        question.followers.append(member)
        return f'You are now following question {idx} <@{member}>!'

    def add(self, askedby, qmsg):
        idx = next(reversed(self.queue), 0) + 1
        self.queue[idx] = QuestionQueue.Question(askedby, qmsg)
        return f'<@{askedby}>: Your question is added at position {len(self.queue)} with index {idx}'

    async def answer(self, ctx, idx, answer=None):
        if idx not in self.queue:
            await ctx.send(f'<@{ctx.author.id}>: No question in the queue with index {idx}!')
        
        elif answer:
            # This is a text-based answer
            qstn = self.queue.pop(idx)
            msg = f'Question {idx} has been answered ' + \
                ', '.join([f'<@{uid}>' for uid in qstn.followers]) + '!\n\n' + \
                    'Question: ' + qstn.qmsg + '\n' + 'Answer: ' + answer
            await ctx.send(msg)
        else:
            # The question will be answered in a voice chat
            cv = getvoicechan(ctx.author)
            if cv is None:
                await ctx.send(f'<@{ctx.author.id}>: Please select a voice channel first where you want to interview the student!')
                return

            qstn = self.queue.pop(idx)
            msg = f'Question {idx} will be answered in voice channel <#{cv.id}> by <@{ctx.author.id}> for ' + \
                ', '.join([f'<@{uid}>' for uid in qstn.followers]) + '!\n'
            await ctx.send(msg)

    def whereis(self, uid):
        qlst = []
        for pos, (idx, qstn) in enumerate(self.queue.items()):
            if uid in qstn.followers:
                if qstn.followers[0] == uid:
                    qlst.append(f'Your own question ({idx}) at position {pos}')
                else:
                    qlst.append(f'Question {idx} at position {pos}')
        if not qlst:
            return f'You are not following questions in this channel <@{uid}>!'
        return f'Questions followed by <@{uid}>:\n' + '\n'.join(qlst) 

class QueueCog(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        Queue.bot = bot
        Queue.datadir = bot.datadir.joinpath('queues')
        if not Queue.datadir.exists():
            Queue.datadir.mkdir()

    def cog_unload(self):
        # Save all queues upon exit
        print('Unloading QueueCog')
        Queue.saveall()
        return super().cog_unload()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def loadallqueues(self, ctx):
        await ctx.send(Queue.loadall())

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
    @commands.has_permissions(administrator=True)
    async def takenext(self, ctx):
        """ Take the next in line from the queue. """
        qid = (ctx.guild.id, ctx.channel.id)
        await self.queues[qid].takenext(ctx)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
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
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
    async def queueme(self, ctx, *args):
        """ Add me to the queue in this channel """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.send(Queue.addtoqueue(qid, ctx.author.id))

    @commands.command(aliases=('ask',))
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def question(self, ctx, *args):
        qid = (ctx.guild.id, ctx.channel.id)
        qmsg = ' '.join(args)
        await ctx.send(Queue.addtoqueue(qid, ctx.author.id, qmsg))

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def answer(self, ctx, idx: int, answer=None):
        ''' Answer a question. '''
        qid = (ctx.guild.id, ctx.channel.id)
        await Queue.queues[qid].answer(ctx, idx, answer)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def follow(self, ctx, idx:int=None):
        ''' Follow a question. '''
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.send(Queue.queues[qid].follow(ctx.author.id, idx))

    @commands.command()
    @commands.check(Queue.qcheck)
    async def whereami(self, ctx):
        """ What's my position in the queue of this channel. """
        uid = ctx.author.id
        await ctx.send(Queue.queues[(ctx.guild.id, ctx.channel.id)].whereis(uid))

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
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
