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
import re
from collections import OrderedDict

import discord
from discord.ext import commands

# Generate regular expressions for raw content parsing
re_ask = re.compile(r'(?:!ask|!question)\s*(.*)')


def getvoicechan(member):
    ''' Get member's voice channel.
        Returns: The members voice channel, or None when not in a channel.
    '''
    return member.voice.channel if member and member.voice else None

def readymovevoice(member):
    ''' Check if this member is ready to be moved to a discussion channel. '''
    return (getvoicechan(member) != None) and not member.voice.self_stream

class Queue:
    ''' Base queue implementation. '''
    # Get reference to bot in a static
    bot = None
    datadir = None
    # Keep queues in a static dict
    queues = dict()

    @classmethod
    def saveall(cls):
        ''' Save all known queues. '''
        print('Saving all queues')
        for qid, queue in cls.queues.items():
            print('Saving queue', qid)
            queue.save()

    @classmethod
    def loadall(cls):
        ''' Load all queue files from disk. '''
        msgs = []
        for qfile in cls.datadir.rglob('*.json'):
            qidstr = qfile.name.replace('.json', '').split('-')
            qid = tuple(int(i) for i in qidstr)
            msgs.append(cls.load(qid))
        return '\n'.join(msgs)

    @classmethod
    async def qcheck(cls, ctx, qtype=''):
        ''' Decorator function to check existence and type of queue. '''
        if 'help' in ctx.message.content:
            return True
        queue = Queue.queues.get((ctx.guild.id, ctx.channel.id), None)
        if queue is None:
            await ctx.send('This channel doesn\'t have a queue!', delete_after=20)
            await ctx.message.delete(delay=20)
            return False
        if not qtype or qtype == queue.qtype or queue.qtype in qtype:
            return True
        await ctx.send(f'{ctx.invoked_with} is not a recognised command for the queue in this channel!', delete_after=20)
        await ctx.message.delete(delay=20)
        return False

    @classmethod
    def makequeue(cls, qid, qtype, guildname, channame):
        ''' Make a new queue, with requested type. '''
        if qid in cls.queues:
            return 'This channel already has a queue!'
        else:
            # Get the correct subclass of Queue
            qclass = next(qclass for qclass in cls.__subclasses__() if qclass.qtype == qtype)
            cls.queues[qid] = qclass(qid, guildname, channame)
            return f'Created a {qtype} queue'

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
        ''' Return the size of this queue. '''
        return len(self.queue)

    async def add(self, ctx, uid):
        ''' Add user with uid to this queue. '''
        # Delete the originating command message
        await ctx.message.delete()
        try:
            pos = self.queue.index(uid)
            msg = f'You are already in the queue <@{uid}>! ' + \
                (f'There are still {pos} people waiting in front of you.' if pos else
                    'You are next in line!')
        except ValueError:
            self.queue.append(uid)
            msg = f'Added <@{uid}> to the queue at position {len(self.queue)}'
        await ctx.send(msg, delete_after=10)

    def remove(self, uid):
        ''' Remove user with uid from this queue. '''
        try:
            self.queue.remove(uid)
        except ValueError:
            return f'<@{uid}> is not listed in the queue!'
        else:
            return f'Removed <@{uid}> from the queue.'

    def fromfile(self, qdata):
        ''' Build queue from data out of json file. '''
        self.queue = qdata

    def tofile(self):
        ''' Return queue data for storage in json file. '''
        return self.queue

    def save(self):
        ''' Save queue object to file. '''
        fname = Queue.datadir.joinpath(f'{self.qid[0]}-{self.qid[1]}.json')
        print('Saving', fname)
        with open(fname, 'w') as fout:
            qjson = dict(qtype=self.qtype,
                         guildname=self.guildname,
                         channame=self.channame,
                         qdata=self.tofile())
            json.dump(qjson, fout, indent=4)

    def whereis(self, uid):
        ''' Find user with id 'uid' in this queue. '''
        try:
            pos = self.queue.index(uid)
            return f'Hi <@{uid}>! ' + \
                (f'There are still {pos} people waiting in front of you.' if pos else
                 'You are next in line!')
        except ValueError:
            return f'You are not in the queue in this channel <@{uid}>!'


class ReviewQueue(Queue):
    qtype = 'Review'

    def __init__(self, qid, guildname, channame):
        super().__init__(qid, guildname, channame)
        self.assigned = dict()
        self.indicator = None
        self.assignments = []

    async def takenext(self, ctx):
        ''' Take the next student from the queue. '''
        # Get the voice channel of the caller
        cv = getvoicechan(ctx.author)
        if cv is None:
            await ctx.send(f'<@{ctx.author.id}>: Please select a voice channel first where you want to interview the student!', delete_after=10)
            return
        if not self.queue:
            await ctx.send(f'<@{ctx.author.id}>: Hurray, the queue is empty!', delete_after=20)
            return

        # Get the next student in the queue
        member = await ctx.guild.fetch_member(self.queue.pop(0))
        unready = []
        while self.queue and not readymovevoice(member):
            await self.bot.dm(member, f'You were invited by a TA, but you\'re not in a voice channel yet!'
                              'You will be placed back in the queue. Make sure that you\'re more prepared next time!')
            # Store the studentID to place them back in the queue, and get the next one to try
            unready.append(member.id)
            if self.queue:
                member = await ctx.guild.fetch_member(self.queue.pop(0))
            else:
                await ctx.send(f'<@{ctx.author.id}> : There\'s noone in the queue who is ready (in a voice lounge)!', delete_after=10)
                self.queue = unready
                return
        # Placement of unready depends on the length of the queue left. Priority goes
        # to those who are ready, but doesn't send unready to the end of the queue.
        if len(self.queue) <= len(unready):
            self.queue += unready
        else:
            insertPos = min(len(self.queue) // 2, 10)
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

    async def putback(self, ctx, pos):
        ''' Put the student you currently have in your voice channel back in the queue. '''
        uid, qid, voicechan = self.assigned.get(
            ctx.author.id, (False, False, False))
        if not uid:
            await ctx.send(f'<@{ctx.author.id}>: You don\'t have a student assigned to you yet!', delete_after=10)
        else:
            self.queue.insert(pos, uid)
            member = await ctx.guild.fetch_member(uid)
            if readymovevoice(member):
                await member.edit(voice_channel=voicechan)
            await self.bot.dm(member, 'You were moved back into the queue, probably because you didn\'t respond.')


    async def updateIndicator(self, ctx):
        '''Floating indicator displaying next in line and length of queue.

        Not a command invoked by a user, but by changes in the queue.'''
        msg = f'**Length of queue:** {len(self.queue)}.\n'+ \
                'Next three in queue:\n'
        for idx, member  in enumerate(self.queue[:3]):
            msg += f'{idx+1}: <@{member}>\n'
        msg += '\n\nType !ready to enter the queue when you\n also want to hand in your assignment!'
        embed = discord.Embed(title=f"Queue for assignments {', '.join(i for i in self.assignments)}",
                              description=msg, colour=0xae8b0c)
        # Delete previous indicator
        if self.indicator is not None:
            await self.indicator.delete()

        # Send new indicator
        self.indicator = await ctx.channel.send(embed=embed)

    async def startReviewing(self, ctx, aid):
        if aid not in self.assignments:
            self.assignments.append(aid)
            self.assignments.sort()
            await self.updateIndicator(ctx)
        else:
            ctx.send(f"Assignment {aid} is already being reviewed.", delete_after=5)

    async def stopReviewing(self, ctx, aid):
        if aid in self.assignments:
            self.assignments.remove(aid)
            await self.updateIndicator(ctx)
        else:
            ctx.send(f"Assignment {aid} was not being reviewed.", delete_after=5)

class MultiReviewQueue(Queue):
    qtype = 'MultiReview'

    class Student:
        def __init__(self, uid):
            self.id = uid
            self.aid = []

    def __init__(self, qid, guildname, channame):
        super().__init__(qid, guildname, channame)
        self.queue = OrderedDict()
        self.studentsQueued = {}
        self.assignments = []
        self.assigned = dict()
        self.indicator = None

    async def convert(self, ctx, singleQueue, aid):
        self.indicator = singleQueue.indicator
        self.assignments = singleQueue.assignments
        if not self.assignments:
            self.assignments.append(aid)
        aid = next(iter(self.assignments))
        self.queue[aid] = singleQueue.queue
        for uid in singleQueue.queue:
            student = MultiReviewQueue.Student(uid)
            student.aid.append(aid)
            self.studentsQueued[uid] = student
        if self.indicator:
            await self.updateIndicator(ctx)


    def fromfile(self, qdata):
        self.queue = qdata['queue']
        self.assignments = qdata['assignments']
        students = OrderedDict()
        for aid in self.assignments:
            for uid in self.queue[aid]:
                if uid in students:
                    students[uid].aid.append(aid)
                else:
                    student = MultiReviewQueue.Student(uid)
                    student.aid.append(aid)
                    students[uid] = student
        self.studentsQueued = students

    def tofile(self):
        qdata = {
            'assignments':self.assignments,
            'queue':self.queue
        }
        return qdata

    async def add(self, ctx, uid, aid=None):
        # Delete the triggering
        try:
            await ctx.message.delete()
        except:
            pass

        # Find if user is already in a queue
        student = self.studentsQueued.get(uid, None)

        # Use !ready to display which assignments they've handed in already
        # Parallels the use of the !follow command in the question queue
        if aid is None:
            msg = ""
            if student is None:
                msg += f'<@{uid}>, you currently have not joined any queues'
                await ctx.channel.send(msg, delete_after=20)
            else:
                readied = student.aid
                plural = (True if len(readied) > 1 else False)
                msg += f'<@{uid}>, are in queue' + \
                       ('s: ' if plural else ': ') + \
                       f'{", ".join(str(i) for i in readied)}' + '. '
                msg += f"You are at position{'s' if plural else ''}:\n"
                for rid in readied:
                    msg += f'{rid}: Position {self.queue[rid].index(uid)+1} of {len(self.queue[rid])}\n'
                await ctx.channel.send(f'<@{uid}>, see your DMs for your queue positions.')
                await self.bot.dm(uid, msg)
            return


        # If student doesn't yet exist, create student
        if student is None:
            student = MultiReviewQueue.Student(uid)
            self.studentsQueued[uid] = student

        # Check queue exists and student not in it
        if aid in self.assignments and aid not in student.aid:
            student.aid.append(aid)
            self.queue[aid].append(student.id)
            msg = f"<@{uid}>, you've been added to assignment {aid}'s queue at position {len(self.queue[aid])}"
        # Queue exists, but student already in it
        elif aid in student.aid:
            pos = self.queue[aid].index(student.id)
            msg = f"Hi <@{student.id}>! For assignmen {aid}, " + \
                (f'there are still {pos} people waiting in front of you.' if pos else
                    'you are next in line!')
        # Queue doesn't exist
        else:
            msg = f"Hi <@{student.id}>! We aren't reviewing that assignment yet, so you'll have to wait until we open that queue."
        self.studentsQueued[uid].aid.sort()
        await ctx.send(msg, delete_after=10)

    def remove(self, uid):
        if uid in self.studentsQueued:
            for aid in self.studentsQueued[uid].aid:
                self.queue[aid].remove(uid)
            self.studentsQueued.pop(uid)
            return f'<@{uid}> removed from the queue.'
        else:
            return f'<@{uid}> is not in any queue!'

    async def takenext(self, ctx, aid=None, prevAll=False):
        ''' Take the next student from the queue. Optionally add the queue number'''
        # In case TAs forget to specify which queue, default to first
        # non-empty queue
        if aid is None:
            aidIter = iter(self.queue)
            aid = next(aidIter)
            while len(self.queue[aid]) == 0:
                aid = next(aidIter)
        # Get the voice channel of the caller
        cv = getvoicechan(ctx.author)
        if cv is None:
            await ctx.send(f'<@{ctx.author.id}>: Please select a voice channel first where you want to interview the student!', delete_after=10)
            return
        if not self.queue[aid]:
            await ctx.send(f'<@{ctx.author.id}>: Hurray, queue {aid} is empty! Might want to check the other ones now', delete_after=20)
            return

        # Get the next student in the queue
        uid = self.queue[aid].pop(0)
        member = await ctx.guild.fetch_member(uid)
        unready = []
        while self.queue[aid] and not readymovevoice(member):
            await self.bot.dm(member.id, f'You were invited by a TA, but you\'re not in a voice channel yet!'
                              'You will be placed back in the queue. Make sure that you\'re more prepared next time!')
            # Store the studentID to place them back in the queue, and get the next one to try
            unready.append(uid)
            if self.queue[aid]:
                uid = self.queue[aid].pop(0)
                member = await ctx.guild.fetch_member(uid)
            else:
                await ctx.send(f'<@{ctx.author.id}> : There\'s noone in queue {aid} who is ready (in a voice lounge)!', delete_after=10)
                self.queue[aid] = unready
                return
        # Placement of unready depends on the length of the queue left. Priority goes
        # to those who are ready, but doesn't send unready to the end of the queue.
        if len(self.queue[aid]) <= len(unready):
            self.queue[aid] += unready
        else:
            insertPos = min(len(self.queue[aid]) // 2, 10)
            self.queue[aid] = self.queue[aid][:insertPos] + unready + self.queue[aid][insertPos:]

        # move the student to the callee's voice channel, and store him/her
        # as assigned for the caller. First remove previous assignee from
        # all queues (assumes they passed all assignments they checked)
        prevStudent = self.assigned.get(ctx.author.id, None)
        if prevStudent:
            if prevAll:
            self.studentsQueued.pop(prevStudent.id)
            for handin in prevStudent.aid:
                self.queue[handin].remove(prevStudent.id)
            else:
                self.queue[aid].remove(prevStudent.id)
            del prevStudent.check
            del prevStudent.oldVC
            del prevStudent.qid

        newStudent = self.studentsQueued[uid]
        newStudent.oldVC = getvoicechan(member)
        newStudent.check = aid
        newStudent.qid = self.qid # I saw in the original putback you pass qid, couldn't see what for
        self.assigned[ctx.author.id] = newStudent
        await member.edit(voice_channel=cv)

        # are there still students in the queue?
        if self.queue[aid]:
            member = await ctx.guild.fetch_member(self.queue[aid][0])
            await self.bot.dm(member,
                              f'Get ready! You\'re next in line for the queue in <#{ctx.channel.id}>!' +
                              ('' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!'))
            if len(self.queue[aid]) > 1:
                # Also send a message to the third person in the queue
                member = await ctx.guild.fetch_member(self.queue[aid][1])
                await self.bot.dm(member,
                                  f'Almost there {member.name}, You\'re second in line for the queue in <#{ctx.channel.id}>!' +
                                  ('' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!'))
            if len(self.queue[aid]) > 5:
                # Also send a message to the fifth person in the queue
                member = await ctx.guild.fetch_member(self.queue[aid][4])
                await self.bot.dm(member,
                                  f'Your patience will soon be rewarded, {member.name}... You\'re fifth in line for the queue in <#{ctx.channel.id}>!' +
                                  '' if getvoicechan(member) else ' Please join a general voice channel so you can be moved!')

    async def putback(self, ctx, pos):
        ''' Put the student you currently have in your voice channel back in the queue. Requires assignment number'''
        student = self.assigned.get(
            ctx.author.id, None)
        if not student:
            await ctx.send(f'<@{ctx.author.id}>: You don\'t have a student assigned to you yet!', delete_after=10)
        else:
            uid = student.id
            for handin in student.aid:
                self.queue[handin].insert(pos, uid)
            member = await ctx.guild.fetch_member(uid)
            if readymovevoice(member):
                await member.edit(voice_channel=student.oldVC)
            await self.bot.dm(member, 'You were moved back into the queue, probably because you didn\'t respond.')

    async def updateIndicator(self, ctx):
        '''Floating indicator displaying next in line and length of queue. Not implemented for MultiReview

        Not a command invoked by a user, but by changes in the queue.'''
        title = "Queue Tracker Widget"
        fieldData = []
        for i in self.assignments:
            fieldname = f'Queue {i}'
            fieldtext = f'**Length of queue:** {len(self.queue[i])}.\n'+ \
                    'Next three in queue:\n'
            for idx, member  in enumerate(self.queue[i][:3]):
                fieldtext += f'{idx+1}: <@{member}>\n'
            fieldData.append((fieldname, fieldtext))
        footer = 'Type `!ready <queue number>` to enter the queue when you also want to hand in your assignment!'


        if fieldData:
            embed = discord.Embed(
                description = "The following queues are active",
                colour = 0xae8b0c
            )
            embed.set_footer(text=footer)

            for ftitle, fcont in fieldData:
                embed.add_field(name=ftitle, value=fcont, inline=True)
        else:
            embed = discord.Embed(
                description = 'As soon as queues open up, you will see which you can join here',
                colour = 0xae8b0c
            )
        embed.set_author(name=title)

        # Delete previous indicator
        if self.indicator is not None:
            await self.indicator.delete()

        # Send new indicator
        self.indicator = await ctx.channel.send(embed=embed)

    async def startReviewing(self, ctx, aid):
        """Adds a queue to the list of allowed queues and updates the indicator"""
        if aid not in self.assignments:
            self.assignments.append(aid)
            self.queue[aid] = []
            self.assignments.sort()
            await self.updateIndicator(ctx)
            await ctx.send(f'Added queue for assignment {aid}', delete_after=5)
        else:
            ctx.send(f"Assignment {aid} is already being reviewed.", delete_after=5)

    async def stopReviewing(self, ctx, aid):
        """Removes a queue, and clears it."""
        if aid in self.assignments:
            for uid in self.queue[aid]:
                self.studentsQueued[uid].aid.remove(aid)
            self.queue.pop(aid)
            self.assignments.remove(aid)
            await self.updateIndicator(ctx)
            await ctx.send(f'Removed queue for assignment {aid}. Queue cleared.', delete_after=5)
        else:
            ctx.send(f"Assignment {aid} was not being reviewed.", delete_after=5)
class QuestionQueue(Queue):
    qtype = 'Question'

    class Question:
        def __init__(self, askedby, qmsg, disc_msg=None):
            self.qmsg = qmsg
            self.disc_msg = disc_msg
            self.followers = [askedby]

    def __init__(self, qid, guildname, channame):
        super().__init__(qid, guildname, channame)
        self.queue = OrderedDict()
        self.answers = dict()
        self.maxidx = 0

    def fromfile(self, qdata):
        ''' Build queue from data out of json file. '''
        idx = -1
        for idx, (qmsg, qf) in enumerate(qdata):
            question = QuestionQueue.Question(0, qmsg)
            question.followers = qf
            self.queue[idx+1] = question
        self.maxidx = idx + 1

    def tofile(self):
        ''' Return queue data for storage in json file. '''
        return [(q.qmsg, q.followers) for q in self.queue.values()]

    async def follow(self, ctx, idx=None):
        """ Follow a question. """
        try:
            await ctx.message.delete()
        except:
            print('Cant delete message in follow')
        if not self.queue:
            await ctx.send('There are no questions in the queue!', delete_after=20)
            return

        member = ctx.author.id
        if idx is None:
            msg = '**The following questions can be followed:**\n\n'
            for qidx, qstn in self.queue.items():
                msg = msg + f'**- {qidx:02d}:** {qstn.qmsg}' + \
                    (' (already following)\n' if member in qstn.followers else '\n')
            embed = discord.Embed(title="Questions in this queue:",
                                  description=msg, colour=0x3939cf)
            await ctx.channel.send(embed=embed, delete_after=30)
            return

        question = self.queue.get(idx, None)
        if question is None:
            msg = f'Hi <@{member}>! There\'s no question in the queue with index {idx}!'
        elif member in question.followers:
            msg = f'You are already following question {idx} <@{member}>!'
        else:
            question.followers.append(member)
            msg = f'You are now following question {idx} <@{member}>!'
        await ctx.send(msg, delete_after=20)

    async def add(self, ctx, askedby, qmsg):
        ''' Add question to this queue. '''
        # Delete the originating command message
        await ctx.message.delete()
        if not qmsg:
            await ctx.send('You can\'t ask without a question!', delete_after=10)
            return
        self.maxidx += 1
        content = f'**Question:** {qmsg}\n\n**Asked by:** <@{askedby}>'
        embed = discord.Embed(title=f"Question {self.maxidx}:",
                              description=content, colour=0xd13b33)  # 0x41f109
        disc_msg = await ctx.send(embed=embed)
        self.queue[self.maxidx] = QuestionQueue.Question(askedby, qmsg, disc_msg)
        msg = f'<@{askedby}>: Your question is added at position {len(self.queue)} with index {self.maxidx}'
        await ctx.send(msg, delete_after=10)

    async def answer(self, ctx, idx, answer=None):
        if idx not in self.queue:
            await ctx.send(f'<@{ctx.author.id}>: No question in the queue with index {idx}!', delete_after=20)

        elif answer:
            # This is a text-based answer
            qstn = self.queue.pop(idx)
            # Delete the question message
            if qstn.disc_msg is not None:
                await qstn.disc_msg.delete()
            # Create the answer message
            content = f'**Question:** {qstn.qmsg}\n\n**Answer:** {answer}\n\n' + \
                  f'**Answered by: **<@{ctx.author.id}>'
            msg = '**Followers:** ' + \
                  ', '.join([f'<@{uid}>' for uid in qstn.followers])
            embed = discord.Embed(title=f"Answer to question {idx}:",
                                  description=content, colour=0x25a52b)  # 0x41f109
            # Store the answer message object for possible later amendments
            qstn.disc_msg = await ctx.channel.send(msg, embed=embed)
            self.answers[idx] = qstn

            # Say something nice if student answers his/her own question
            if qstn.followers[0] == ctx.author.id:
                await ctx.send(f'Well done <@{ctx.author.id}>! You solved your own question!', delete_after=20)

        else:
            # The question will be answered in a voice chat
            cv = getvoicechan(ctx.author)
            if cv is None:
                await ctx.send(f'<@{ctx.author.id}>: Please select a voice channel first where you want to interview the student!', delete_after=20)
                return

            qstn = self.queue.pop(idx)
            if qstn.disc_msg is not None:
                await qstn.disc_msg.delete()
            content = f'**Question:** {qstn.qmsg}\n\nQuestion {idx} will be answered in voice channel <#{cv.id}>\n\n' + \
                f'**Answered by: **<@{ctx.author.id}>'
            embed = discord.Embed(title=f"Answer to question {idx}:",
                                  description=content, colour=0x25a52b)
            msg = '**Followers:** ' + \
                  ', '.join([f'<@{uid}>' for uid in qstn.followers])
            # Store the answer message object for possible later amendments
            qstn.disc_msg = await ctx.channel.send(msg, embed=embed)
            self.answers[idx] = qstn

    async def amend(self, ctx, idx, amendment=''):
        ''' Amend the answer to question with index idx. '''
        qstn = self.answers.get(idx, None)
        if qstn is None:
            await ctx.send(f'<@{ctx.author.id}>: No answered question found with index {idx}', delete_after=20)
            return

        msg = qstn.disc_msg
        embed = msg.embeds[0]
        title = embed.title
        colour = 0x2cc533 #embed.colour
        content = embed.description
        inspos = content.find('**Answered by: **')
        # Delete the original answer
        await msg.delete()
        # and create an amended one
        newcontent = content[:inspos] + f'**Amendment from <@{ctx.author.id}>: ** {amendment}\n\n' + content[inspos:]
        newembed = discord.Embed(title=title,
                                 description=newcontent, colour=colour)
        msg = '**Followers:** ' + \
            ', '.join([f'<@{uid}>' for uid in qstn.followers])
        qstn.disc_msg = await ctx.channel.send(msg, embed=newembed)

    def whereis(self, uid):
        ''' Find questions followed by user with id 'uid' in this queue. '''
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
        ''' Load all queues that were previously stored to disk. '''
        await ctx.send(Queue.loadall())

    @commands.group(invoke_without_command=True)
    @commands.check(lambda ctx: Queue.qcheck(ctx, ['Review', 'MultiReview']))
    @commands.has_permissions(administrator=True)
    async def takenext(self, ctx, aid=None):
        """ Take the next in line from the queue.

        Optional argument:
         - aid: supply which assignment was checked for previous student.

        Optional subcommand:
         - `!takenext all` removes previous student from all queues."""
        qid = (ctx.guild.id, ctx.channel.id)
        try:
            await ctx.message.delete()
        except:
            pass
        if aid:
            await Queue.queues[qid].takenext(ctx, aid)
        else:
        await Queue.queues[qid].takenext(ctx)
        await Queue.queues[qid].updateIndicator(ctx)

    @takenext.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'MultiReview'))
    @commands.has_permissions(administrator=True)
    async def all(self,ctx, aid=None):
        qid = (ctx.guild.id, ctx.channel.id)
        try:
            await ctx.message.delete()
        except:
            pass
        await Queue.queues[qid].takenext(ctx,aid,True)
        await Queue.queues[qid].updateIndicator(ctx)


    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, ['Review', 'MultiReview']))
    @commands.has_permissions(administrator=True)
    async def putback(self, ctx, pos : int = 10):
        ''' Put the student you currently have in your voice channel back in the queue.

            Arguments:
            - pos: The position in the queue to put the student. (optional)
              Default position is 10. '''
        qid = (ctx.guild.id, ctx.channel.id)
        try:
            await ctx.message.delete()
        except:
            pass
        await Queue.queues[qid].putback(ctx, pos)
        await Queue.queues[qid].updateIndicator(ctx)

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def makequeue(self, ctx, qtype='Review'):
        """ Make a queue in this channel.

            Arguments:
            - qtype: The type of queue to create. (optional, default=Review)
        """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.message.delete()
        await ctx.send(Queue.makequeue(qid, qtype, ctx.guild.name, ctx.channel.name))

    @commands.command()
    @commands.check(Queue.qcheck)
    @commands.has_permissions(administrator=True)
    async def savequeue(self, ctx):
        """ Save the queue in this channel. """
        await ctx.message.delete()
        Queue.queues[(ctx.guild.id, ctx.channel.id)].save()

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def loadqueue(self, ctx):
        """ Load this channel's queue from disk. """
        await ctx.send(Queue.load((ctx.guild.id, ctx.channel.id)))

    @commands.command(aliases=('ready', 'done'))
    @commands.check(lambda ctx: Queue.qcheck(ctx, ['Review', 'MultiReview']))
    async def queueme(self, ctx, *args):
        """ Add me to the queue in this channel. """
        qid = (ctx.guild.id, ctx.channel.id)
        if len(args)>0:
            await Queue.queues[qid].add(ctx, ctx.author.id, args[0])
        else:
            await Queue.queues[qid].add(ctx, ctx.author.id)
        await Queue.queues[qid].updateIndicator(ctx)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, ['Review', 'MultiReview']))
    async def removeme(self, ctx, *args):
        """ Remove me from the queue in this channel. """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.message.delete()
        await ctx.send(Queue.queues[qid].remove(ctx.author.id), delete_after=10)
        await Queue.queues[qid].updateIndicator(ctx)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, ['Review', 'MultiReview']))
    @commands.has_permissions(administrator=True)
    async def remove(self, ctx, member: discord.Member):
        """ Remove user from the queue in this channel.

            Arguments:
            - @user: Mention the user to remove from the queue.
        """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.message.delete()
        await ctx.send(Queue.queues[qid].remove(member.id), delete_after=10)
        await Queue.queues[qid].updateIndicator(ctx)

    @commands.command('ask', aliases=('question',), rest_is_raw=True)
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def question(self, ctx):
        """ Ask a question in this channel.

            Arguments:
            - question: The question you want to ask.
        """
        qid = (ctx.guild.id, ctx.channel.id)
        qmsg = re_ask.match(ctx.message.content).groups()[0]
        await Queue.queues[qid].add(ctx, ctx.author.id, qmsg)

    @commands.command(rest_is_raw=True)
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def answer(self, ctx, idx: int):
        ''' Answer a question.

            Arguments:
            - idx: The index number of the question you want to answer
            - answer: The answer to the question (optional: if no answer is
              given, followers are invited to your voice channel)
        '''
        qid = (ctx.guild.id, ctx.channel.id)
        offset = ctx.message.content.index(str(idx))+len(str(idx))
        ansstring = ctx.message.content[offset:].strip()
        await ctx.message.delete()
        await Queue.queues[qid].answer(ctx, idx, ansstring)

    @commands.command(rest_is_raw=True)
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def amend(self, ctx, idx: int):
        ''' Amend an answer.

            Arguments:
            - idx: The index number of the answered question you want to amend
            - amendment: The text you want to add to the answer
        '''
        qid = (ctx.guild.id, ctx.channel.id)
        offset = ctx.message.content.index(str(idx))+len(str(idx))
        amstring = ctx.message.content[offset:].strip()
        await ctx.message.delete()
        await Queue.queues[qid].amend(ctx, idx, amstring)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Question'))
    async def follow(self, ctx, idx: int = None):
        ''' Follow a question.

            Arguments:
            - idx: The index of the question to follow (optional: if no index
              is given a list of questions is printed).
        '''
        qid = (ctx.guild.id, ctx.channel.id)
        await Queue.queues[qid].follow(ctx, idx)

    @commands.command()
    @commands.check(Queue.qcheck)
    async def whereami(self, ctx):
        """ What's my position in the queue of this channel. """
        uid = ctx.author.id
        await ctx.message.delete()
        await ctx.send(Queue.queues[(ctx.guild.id, ctx.channel.id)].whereis(uid), delete_after=10)

    @commands.command()
    @commands.check(lambda ctx: Queue.qcheck(ctx, 'Review'))
    @commands.has_permissions(administrator=True)
    async def queue(self, ctx, *, member: discord.Member = None):
        """ Admin command: check and add to the queue.

            Arguments:
            - @user mention: Mention the user you want to add to the queue (optional:
              if no user is given, the length of the queue is returned).
        """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.message.delete()
        if member is None:
            # Only respond with the length of the queue
            size = Queue.queues[qid].size()
            await ctx.send(f'There are {size} entries in the queue of <#{ctx.channel.id}>', delete_after=10)
        else:
            # Member is passed, add him/her to the queue
            await Queue.queues[qid].add(ctx, member.id)
        await Queue.queues[qid].updateIndicator(ctx)

    @commands.command('toggle', aliases=('toggleReview',))
    @commands.check(lambda  ctx: Queue.qcheck(ctx, ['Review', 'MultiReview']))
    @commands.has_permissions(administrator=True)
    async def toggleReview(self, ctx, aid):
        """Toggles whether an assignment is being handled

        In a ReviewQueue this merely indicates in the Indicator if it's being accepted.
        In a MultiReviewQueue this adds and removes queues.
        Arguments:
            - aid: Assignment number.
        """
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.message.delete()
        if aid is None:
            await ctx.send(f'Command requires an assignment number', delete_after=5)
        elif aid in Queue.queues[qid].assignments:
            await Queue.queues[qid].stopReviewing(ctx, aid)
        else:
            await Queue.queues[qid].startReviewing(ctx, aid)

    @commands.command('convert')
    @commands.check(lambda  ctx: Queue.qcheck(ctx, 'Review'))
    @commands.has_permissions(administrator=True)
    async def convert(self, ctx, aid='1'):
        """Function to convert from Review to MultiReview

        Arguments:
            - aid: Assignment number for first queue, if none already enabled.
              Defaults to 1"""
        qid = (ctx.guild.id, ctx.channel.id)
        await ctx.message.delete()
        if Queue.queues[qid].qtype == 'Review':
            targetQType = 'MultiReview'
        else:
            targetQType = 'Review' # Requires ReviewQueue to have a convert method
        oldQueue = Queue.queues[qid]
        Queue.queues.pop(qid)
        newQueue = Queue.makequeue(qid, targetQType, ctx.guild.name, ctx.channel.name)
        await Queue.queues[qid].convert(ctx, oldQueue, aid)
