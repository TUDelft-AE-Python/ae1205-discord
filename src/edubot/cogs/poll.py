import asyncio
import pickle
import io
import json
import discord
import emoji  # Library used for handling emoji codes
import matplotlib.pyplot as plt
import numpy as np
from discord.ext import commands
from matplotlib.ticker import PercentFormatter

# Define a shorthand for obtaining the emoji belonging to a :emoji: string
get_emoji = lambda em: emoji.emojize(em, use_aliases=True)


class Quiz:

    """
    Class used to store all details related to a quiz: answers, question, votes and correct answer.
    Also contains information about the quiz message and creator for use by the Discord API
    """

    def __init__(self,name,json_file, owner):
        self.name = name
        self.filename = json_file
        self.owner = owner

        self.message_id = None
        self.channel_id = None

        self.question = ""
        self.correct_answer = 0
        self.options = {}
        self.timer = None

        self.votes = {}

        self.emoji_options = [get_emoji(em) for em in
                              (":one:",":two:",":three:",":four:",":five:",":six:",":seven:",":eight:",":nine:")]

    def load_data(self):

        '''Function for loading in json files containing the quiz information'''
        try:
            with open(self.filename, "r") as file:
                json_data = json.load(file)

            self.question = str(json_data["question"])
            self.options = {i+1: str(option) for i,option in enumerate(json_data["options"])}

            correct = str(json_data["correct"])
            self.correct_answer = None if len(correct) == 0 or correct in ("0","-1") else int(correct)
            self.votes = {i+1: [] for i in range(len(self.options))}

            # When the  file is read in, the timer specified there is used as a baseline. !makequiz and !startquiz
            # Can overwrite this value
            if "timer" in json_data:
                timer_val = str(json_data["timer"])
                self.timer = None if len(timer_val) == 0 or timer_val in ("0","-1") else int(timer_val)

            succesful = True

        except Exception:
            succesful = False

        return succesful, self

    def generate_quiz_message(self):

        '''Function for generating all required parameters for a Discord message Embed to represent the quiz'''

        title = self.name
        question = self.question

        answer_options = "\n".join([f"{i+1}) {self.options[option]}" for i,option in enumerate(self.options)])

        informational_text = "Answer with the emoji's given below. Only your final answer counts!"

        description = "\n\n".join([question, answer_options, informational_text])

        emojis = [self.emoji_options[i] for i in range(len(self.options))]

        return title, description, emojis

    def vote(self, voter_id, emoji):

        '''Function that handles user votes to the quiz and makes sure each user only has one final vote'''

        # If it's an invalid emoji, just return
        if not emoji in self.emoji_options:
            return

        # Delete the voter_id from all options
        for option in self.votes:
            if voter_id in self.votes[option]:
                self.votes[option].remove(voter_id)
        # Cast the vote
        self.votes[self.emoji_options.index(emoji) + 1].append(voter_id)


    def create_histogram(self):

        """
        Function that creates a histogram to serve as quiz feedback, shows percentual distribution of votes.
        Returns a BytesIO() object that serves as an image file to pass into a Discord message.
        """

        # Create a BytesIO buffer to temporarily store the image
        image_buffer = io.BytesIO()
        image_buffer.name = f"{self.name}_quiz_feedback.png"

        # Set the plot style to be easier to view in Discord
        plt.style.use('dark_background')

        # Get the distribution of votes in percentages
        individual_votes = np.array([len(self.votes[option]) for option in self.options])
        if np.sum(individual_votes) != 0:
            weighted_votes = individual_votes / np.sum(individual_votes) * 100
        else:
            weighted_votes = np.zeros(len(self.options)) * 100

        # Create a bar chart to represent the data
        barchart = plt.bar(np.array(range(1,len(self.options) + 1)), weighted_votes, width=0.4, color="r")
        plt.ylim((0,100))
        plt.gca().yaxis.set_major_formatter(PercentFormatter())
        plt.xticks(np.array(range(1, len(self.options) + 1)))
        plt.xlabel("Answers")

        # Color the correct answer green
        if self.correct_answer:
            barchart.patches[self.correct_answer - 1].set_facecolor("g")
        else:
            for patch in barchart.patches:
                patch.set_facecolor("b")

        # Show the values of the various bars in the bar chart above the bars
        for bar in barchart:
            height = round(bar.get_height(),2)
            plt.gca().text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2, f"{height}%",
                           ha='center', color='white', fontsize=15)

        # Disable the left and top splines
        [spine.set_visible(False) for i, spine in enumerate(list(plt.gca().spines.values())) if i in (1,3)]
        plt.tick_params(bottom='off', left='off', labelleft='off', labelbottom='on')

        # Save figure to image buffer
        plt.savefig(image_buffer, format="png", bbox_inches="tight", transparent=True)
        plt.close()

        # Reset the buffer internal index to the beginning
        image_buffer.seek(0)

        return image_buffer





class Poll(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.datadir = bot.datadir.joinpath('quizzes')
        if not self.datadir.exists():
            self.datadir.mkdir()

        self.save_filepath = self.datadir.joinpath("saved_quizzes.pickle")

        # This dictionary contains all the currently active quizzes
        self.quizzes = {}
        self.load_quizzes()

    def cog_unload(self):

        '''Function to handle unloading of the Poll Cog'''

        # Save all active quizzes before shutdown
        print('Unloading Poll Cog')
        self.save_quizzes()
        return super().cog_unload()

    def save_quizzes(self):

        '''Function to save a pickle object containing all the currently active quizzes'''

        with open(self.save_filepath, 'wb') as file:
            pickle.dump(self.quizzes, file)

    @commands.command("savequiz",aliases=("save-quiz","save_quiz","savequizzes","save-quizzes","save_quizzes"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def save_quiz(self,ctx):
        self.save_quizzes()
        await ctx.channel.send(f"<@{ctx.author.id}> Currently active quizzes saved!",
                               delete_after=3)
        await ctx.message.delete()

    def load_quizzes(self):

        '''Function to load the pickle object containing all the currently active quizzes'''

        # If it doesn't exist, there is nothing to load.
        if not self.save_filepath.exists():
            self.save_quizzes()
            return
        with open(self.save_filepath, 'rb') as file:
            self.quizzes = pickle.load(file)

    @commands.command("startquiz", aliases=("start-quiz","start_quiz","quiz","beginquiz","begin-quiz",
                                            "begin_quiz","launchquiz","launch_quiz","launch-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def start_quiz(self,ctx,*args):

        '''Discord command to create a Quiz object and represent it in Discord'''

        # Save the channel in which the message was sent
        quiz_channel = ctx.channel
        # Save the creator's id to privately send feedback after the quiz is finished
        quiz_creator = ctx.author.id

        # Delete the message containing the command
        await ctx.message.delete()

        try:
            quiz_filename = args[0]
            quiz_name = " ".join(args[1:])
            timer_value = None
            if len(quiz_name) == 0:
                raise Exception

            # A timer value has also been specified, which must be extracted before proceeding.
            if "timer=" in quiz_name.lower():
                timer_value = int(args[-1].lower().strip("timer="))
                timer_value = timer_value if timer_value > 0 else None
                quiz_name = " ".join(args[1:-1])

        except Exception:
            await ctx.channel.send(
                f"<@{ctx.author.id}> Command used incorrectly! Please provide the filename first, then the quiz name. "
                f"Optionally, a time limit can be specified using timer=xx",
                delete_after=3
            )
            return

        # Add a .json extension if it is not present
        if not ".json" in quiz_filename:
            quiz_filename += ".json"

        quiz_filepath = self.datadir.joinpath(quiz_filename)

        # Check if the filename specified actually exists
        if not quiz_filepath.exists():
            await ctx.channel.send(
                f"<@{ctx.author.id}> The filename provided does not seem to exist, please check spelling and try again.",
                delete_after=3
            )
            return

        # Create the new quiz
        was_succesful, new_quiz = Quiz(quiz_name,quiz_filepath,quiz_creator).load_data()

        # Abort if the data reading has failed. If the bot has been properly configured, this means that the json
        # formatting is wrong.
        if not was_succesful:
            await ctx.channel.send(
                f"<@{ctx.author.id}> The json quiz file has been improperly formatted!",
                delete_after=5
            )
            return

        if timer_value:
            new_quiz.timer = timer_value

        # Create the message belonging to the quiz and give it a green coloured embed
        title, description, emojis = new_quiz.generate_quiz_message()
        embed = discord.Embed(title=title, description=description, colour=0x41f109)
        new_message = await quiz_channel.send(embed=embed)

        # Now attach this new message's id to the new quiz
        new_quiz.message_id = new_message.id
        new_quiz.channel_id = new_message.channel.id

        # Add the quiz to the internal dict
        self.quizzes[new_quiz.message_id] = new_quiz

        # Add the appropriate reactions
        for em in emojis:
            await new_message.add_reaction(em)

        # If the quiz has a timer, activate it
        if new_quiz.timer:
            self.bot.loop.create_task(self.quiz_timer(new_quiz.timer,new_message))


    @commands.command("finishquiz", aliases=("finish-quiz", "finish_quiz", "endquiz","end_quiz","end-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def finish_quiz(self,ctx,*args):

        """
        Discord command to end a quiz and publish its results using the Quiz create_histogram function.
        It sends the histogram to the channel where the quiz resides as well as the people who started
        and ended the quiz.
        """
        # If this is the case, then this was not an internal function call and it was an actual command
        if not type(ctx) == int:
            # Save the author and channel for future reference
            author_id = ctx.author.id
            message_channel = ctx.channel

            # Delete the message containing the command
            await ctx.message.delete()

            quiz_name = " ".join(args)

            try:
                quiz_to_finish = self.quizzes[list(filter(lambda k: self.quizzes[k].name, self.quizzes))[0]]
            except Exception:
                await ctx.channel.send(
                    f"<@{ctx.author.id}> That quiz does not exist, please check the spelling of the name you provided!",
                    delete_after=3
                )
                return

        # The function was called internally by quiz_timer
        else:
            # Check if the quiz has been ended in the meantime
            if not ctx in self.quizzes:
                return
            quiz_to_finish = self.quizzes[ctx]
            author_id = quiz_to_finish.owner
            message_channel = self.bot.get_channel(quiz_to_finish.channel_id)

        feedback_chart = quiz_to_finish.create_histogram()

        file_object = discord.File(feedback_chart, filename=feedback_chart.name)
        embed = discord.Embed(title=f"Feedback for {quiz_to_finish.name}", colour=0x41f109)
        embed.set_image(url=f"attachment://{feedback_chart.name}")

        # Send the feedback chart to the channel where the quiz is located
        await self.bot.get_channel(quiz_to_finish.channel_id).send(embed=embed,file=file_object)

        # Send the feedback chart to the person who created the quiz and the person who ended it
        for user_id in {author_id, quiz_to_finish.owner}:
            # Reset the buffer internal index to 0 again
            feedback_chart.seek(0)
            await message_channel.guild.get_member(user_id).send(embed=embed,file=file_object)
        # Remove the quiz from the internal dictionary
        self.quizzes.pop(quiz_to_finish.message_id)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,ctx):

        '''A Discord event listener that is triggered each time a reaction is added to a message.'''

        message_id = ctx.message_id
        if not message_id in self.quizzes or ctx.user_id == self.bot.user.id:
            return
        # The RawReactionEvent object only contains id's, so these need to be converted to usable
        # discord Channel, Message and Member objects in order to delete the received reaction
        reaction_channel = self.bot.get_channel(ctx.channel_id)
        reaction_message = await reaction_channel.fetch_message(message_id)
        reaction_member = reaction_channel.guild.get_member(ctx.user_id)
        await reaction_message.remove_reaction(ctx.emoji, reaction_member)

        # Call the vote command. If an invalid emoji has been used, this will do nothing
        self.quizzes[message_id].vote(reaction_member.id, str(ctx.emoji))

    @commands.command("makequiz", aliases=("make_quiz","make-quiz","create-quiz","create_quiz","createquiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def create_quiz(self,ctx, *args):

        '''Function to create a quiz json file using either a file attachment or a json string directly'''

        if len(args) == 0:
            await ctx.channel.send(f"<@{ctx.author.id}> No arguments were given!",
                                   delete_after=3)
            await ctx.message.delete()
            return

        # If a file has been attached, this means the quiz is attached in a json file format
        if len(ctx.message.attachments) > 0:
            # In this case, the command usage dictates that the argument is the filename that should be used
            # to save the json file.
            file_name = " ".join(args).rstrip(".json")
            file_name += ".json"
            await ctx.message.attachments[0].save(self.datadir.joinpath(file_name), use_cached=False, seek_begin=True)
            await ctx.message.delete()
            return

        # If not, the json data must be given as an argument
        if not len(args) >= 4:
            await ctx.channel.send(f"<@{ctx.author.id}> Incorrect usage of command! Either attach the json file to "
                                   f"the message and provide the filename as argument or provide filename, question, "
                                   f"answers and correct response as separate arguments.",
                                   delete_after=6)
            await ctx.message.delete()
            return
        timer_value = ''
        # A timer value was added, which needs to be extracted now
        if len(args) == 5:
            timer_value = f', "timer":{args[4].lower().strip("timer=")}'
            args = args[:-1]

        question = args[1]
        correct = args[-1]
        options_parsed = args[-2].split(";")
        options_parsed = ','.join([f'"{opt}"' for opt in options_parsed])

        file_name = args[0].rstrip(".json") + ".json"
        json_string = f'{{"question": "{question}", "options": [{options_parsed}], "correct": "{correct}"{timer_value}}}'

        with open(self.datadir.joinpath(file_name), 'w') as file:
            file.write(json_string)

        await ctx.message.delete()

    @commands.command("view-quizzes", aliases=("viewquizzes", "view_quizzes", "view_quiz", "viewquiz", "view-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def view_quizzes(self,ctx):

        '''Function to list all stored json files as well as all active quizzes'''

        json_files = [path.name for path in list(self.datadir.rglob("*.json"))]
        currently_active = [self.quizzes[message_id].name for message_id in self.quizzes]
        to_send = "Quiz JSON files: \n- "*(len(json_files)>0) + "\n- ".join(json_files) + "\n\n" + \
            "Currently active quizzes: \n- "*(len(currently_active) > 0) + "\n- ".join(currently_active)


        # Check if the string is empty
        if len(to_send.strip()) == 0:
            await ctx.channel.send(f"<@{ctx.author.id}> There are no json files stored and no quizzes active.",
                                   delete_after=4)
        else:
            embed = discord.Embed(title="Quiz JSON files and active quizzes", description=to_send, colour=0x41f109)
            await ctx.channel.send(embed=embed, delete_after=30)
        await ctx.message.delete()

    @commands.command("inspect_quiz", aliases=("inspectquiz","inspect-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def inspect_quiz_json(self,ctx,*args):

        '''Function to send stored json file via private message to the user'''

        filename = (" ".join(args)).rstrip(".json") + ".json"
        filepath = self.datadir.joinpath(filename)
        if not filepath.exists():
            await ctx.channel.send(f"<@{ctx.author.id}> That file does not exist!",
                                   delete_after=4)
        else:
            await ctx.channel.send(f"<@{ctx.author.id}> File will be sent via private message.",
                                   delete_after=4)
            await self.bot.get_user(ctx.author.id).send(f"<@{ctx.author.id}> Here is the file that you requested.",
                                                        file=discord.File(filepath))
        await ctx.message.delete()

    @commands.command("delete-quiz", aliases=("deletequiz","delete_quiz","removequiz","remove-quiz","remove_quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def remove_quiz(self,ctx,*args):

        '''Function to remove a stored json file'''

        filename = (" ".join(args)).rstrip(".json") + ".json"
        filepath = self.datadir.joinpath(filename)
        if not filepath.exists():
            await ctx.channel.send(f"<@{ctx.author.id}> That file does not exist!",
                                   delete_after=4)
        else:
            filepath.unlink()
            await ctx.channel.send(f"<@{ctx.author.id}> File deleted!",
                                   delete_after=3)
        await ctx.message.delete()


    async def quiz_timer(self, timer_duration, message_object):

        '''Function to dynamicall update the timer value on a quiz and automatically end it'''

        timer = timer_duration
        t = lambda x: f"{0 if x//60 < 10 else ''}{x // 60}:{0 if x % 60 < 10 else ''}{x % 60}{0 if x % 60 == 0 else ''}"

        # Extract the embed from the message and get it's original title
        embed = message_object.embeds[0]

        while timer > 0:
            new_timer_value = f"Time left: {t(timer)}"
            embed.set_footer(text=new_timer_value)
            await message_object.edit(embed=embed)
            await asyncio.sleep(1)
            timer -= 1

        await self.finish_quiz(message_object.id)
