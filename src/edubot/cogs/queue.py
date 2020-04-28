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
import json
from collections import OrderedDict

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
            qidstr = qfile.name.replace('.json', '').split('-')
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
    def makequeue(cls, qid, qtype, guildname, channame):
        if qid in cls.queues:
            return 'This channel already has a queue!'
        else:
            # Get the correct subclass of Queue
            qclass = next(qclass for qclass in cls.__subclasses__() if qclass.qtype == qtype)
            cls.queues[qid] = qclass(qid, guildname, channame)
            return f'Created a {qtype} queue'

    @classmethod
    def addtoqueue(cls, qid, *args):
        return cls.queues[qid].add(*args)

    @classmethod
    def load(cls, qid):
        ''' Load queue object from file. '''
        try:
            fname = cls.datadir.joinpath(f'{qid[0]}-{qid[1]}.json')
            with open(fname, 'r') as fin:
                qjson = json.load(fin)
                qtype = qjson['qtype']
                cls.makequeue(qid, qtype, qjson['guildname'], qjson['channame'])
                cls.queues[qid].fromfile(qjson['qdata'])
                return f'Loaded a {qtype} queue for <#{qid[1]}> in {cls.queues[qid].guildname} with {cls.queues[qid].size()} entries.'
        except IOError:
            return 'No saved queue available for this channel.'

    def __init__(self, qid, guildname, channame):
        self.qid = qid
        self.guildname = guildname
        self.channame = channame
        self.queue = []

    def size(self):
        return len(self.queue)

    def add(self, *args):
        return ''

    def fromfile(self, fin):
        ''' Build queue from data out of json file. '''
        pass

    def tofile(self, fout):
        ''' Return queue data for storage in json file. '''
        pass

    def save(self):
        ''' Save queue object to file. '''
        fname = Queue.datadir.joinpath(f'{self.qid[0]}-{self.qid[1]}.json')
        print('Saving', fname)
        with open(fname, 'w') as fout:
            qjson = dict(qtype=self.qtype,
                         guildname=self.guildname,
                         channame=self.channame,
                         qdata=self.tofile())
            json.dump(qjson, fout)

    def whereis(self, uid):
        pass


class ReviewQueue(Queue):
    qtype = 'Review'

    def __init__(self, qid, guildname, channame):
        super().__init__(qid, guildname, channame)
        self.assigned = dict()

    def fromfile(self, qdata):
        ''' Build queue from data out of json file. '''
        self.queue = qdata

    def tofile(self):
        ''' Return queue data for storage in json file. '''
        return self.queue

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
        unready = []
        while count > 0 and not getvoicechan(member):
            count -= 1
            await self.bot.dm(member, f'You were invited by a TA, but you\'re not in a voice channel yet!'
                              'You will be placed back in the queue. Make sure that you\'re more prepared next time!')
            # Store the studentID to place them back in the queue, and get the next one to try
            unready.append(member)
            if count:
                member = await ctx.guild.fetch_member(self.queue.pop(0))
            else:
                await ctx.send(f'<@{ctx.author.id}> : There\'s noone in the queue who is ready (in a voice lounge)!')
                self.queue = unready
                return
        # Placement of unready depends on the length of the queue left. Priority goes
        # to those who are ready, but doesn't send unready to the end of the queue.
        if count <= len(unready):
            self.queue += unready
        else:
            insertPos = min(count // 2, 10)
            self.queue = self.queue[:insertPos] + unready + self.queue[insertPos:]

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
            if len(self.queue) > 5:
                # Also send a message to the fifth person in the queue
                member = await ctx.guild.fetch_member(self.queue[4])
                await self.bot.dm(member,
                                  f'Your patience will soon be rewarded, {member.name}... You\'re fifth in line for the queue in <#{ctx.channel.id}>!' +
                                  '' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!')

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

    async def fromhistory(self, ctx):
        # Fill queue from message history, and clean channel
        deleted = 0
        skipped = 0
        queued  = 0
        await ctx.channel.send('Parsing old messages...')
        async for message in ctx.channel.history(limit=None, oldest_first=True):
            print(message.content.casefold())
            if message.content.casefold().startswith('ready'):
                checked = False
                for reaction in message.reactions:
                    if reaction.emoji == '✅':
                        checked = True
                if checked:
                    await message.delete()
                    deleted += 1
                else:
                     # avoid queueing someone twice
                    self.add(message.author.id)
                    queued += 1
            # clean up old commands
            elif message.content.startswith('!'):
                await message.delete()
                deleted += 1
            # if not student saying ready, check if TA/Tutor message
            elif len(message.author.roles) == 2 and not message.author.bot:
                skipped += 1
                pass
            # not TA/Tutor, not student getting ready. Ergo clutter
            else:
                await message.delete()
                deleted += 1
        await ctx.channel.send(f'Messages..  ..deleted: {deleted} ..queued: {queued} ..skipped: {skipped}',delete_after=2)


class QuestionQueue(Queue):
    qtype = 'Question'

    class Question:
        def __init__(self, askedby, qmsg):
            self.qmsg = qmsg
            self.followers = [askedby]

    def __init__(self, qid, guildname, channame):
        super().__init__(qid, guildname, channame)
        self.queue = OrderedDict()

    def fromfile(self, qdata):
        ''' Build queue from data out of json file. '''
        for idx, (qmsg, qf) in enumerate(qdata):
            question = QuestionQueue.Question(0, qmsg)
            question.followers = qf
            self.queue[idx+1] = question

    def tofile(self):
        ''' Return queue data for storage in json file. '''
        return [(q.qmsg, q.followers) for q in self.queue.values()]

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
        await Queue.queues[qid].takenext(ctx)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
    @commands.has_permissions(administrator=True)
    async def putback(self, ctx):
        ''' Put the student you currently have in your voice channel back in the queue. '''
        qid = (ctx.guild.id, ctx.channel.id)
        await Queue.queues[qid].putback(ctx)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def makequeue(self, ctx, qtype='Review'):
        """ Make a queue in this channel. """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.send(Queue.makequeue(qid, qtype, ctx.guild.name, ctx.channel.name))

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
    @commands.has_permissions(administrator=True)
    async def fromhistory(self, ctx):
        """ Populate the queue in this channel from normal ready messages in
            the channel history. """
        qid = (ctx.guild.id, ctx.channel.id)
        await Queue.queues[qid].fromhistory(ctx)

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
        ctx.message.delete()
        await ctx.send(Queue.addtoqueue(qid, ctx.author.id), delete_after=4)

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
    async def follow(self, ctx, idx: int = None):
        ''' Follow a question. '''
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.send(Queue.queues[qid].follow(ctx.author.id, idx))

    @commands.command()
    @commands.check(Queue.qcheck)
    async def whereami(self, ctx):
        """ What's my position in the queue of this channel. """
        uid = ctx.author.id
        await ctx.message.delete()
        await ctx.send(Queue.queues[(ctx.guild.id, ctx.channel.id)].whereis(uid), delete_after=4)

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
            await ctx.send(Queue.addtoqueue(qid, member.id))
