import asyncio
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

    def __init__(self, json_file, owner):
        self.name = 'Quiz'
        self.filename = json_file
        self.owner = owner

        self.message_id = None
        self.channel_id = None

        self.question = ""
        self.correct_answer = 0
        self.options = {}
        self.timer = None

        self.votes = {}
        self.singlevote = True

        self.emoji_options = [get_emoji(em) for em in
                              (":one:",":two:",":three:",":four:",":five:",":six:",":seven:",":eight:",":nine:",
                               ":keycap_ten:", "\N{REGIONAL INDICATOR SYMBOL LETTER A}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER B}", "\N{REGIONAL INDICATOR SYMBOL LETTER C}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER D}", "\N{REGIONAL INDICATOR SYMBOL LETTER E}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER F}", "\N{REGIONAL INDICATOR SYMBOL LETTER G}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER H}", "\N{REGIONAL INDICATOR SYMBOL LETTER I}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER J}", "\N{REGIONAL INDICATOR SYMBOL LETTER K}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER L}", "\N{REGIONAL INDICATOR SYMBOL LETTER M}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER N}", "\N{REGIONAL INDICATOR SYMBOL LETTER O}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER P}", "\N{REGIONAL INDICATOR SYMBOL LETTER Q}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER R}", "\N{REGIONAL INDICATOR SYMBOL LETTER S}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER T}", "\N{REGIONAL INDICATOR SYMBOL LETTER U}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER V}", "\N{REGIONAL INDICATOR SYMBOL LETTER W}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER X}", "\N{REGIONAL INDICATOR SYMBOL LETTER Y}",
                               "\N{REGIONAL INDICATOR SYMBOL LETTER Z}")]

    def load_data(self):
        '''Function for loading in json files containing the quiz information'''
        try:
            with open(self.filename, "r") as file:
                json_data = json.load(file)
            self.name = json_data.get('name', 'Quiz')
            self.question = str(json_data["question"])
            self.options = {i+1: str(option) for i,option in enumerate(json_data["options"])}

            self.correct_answer = json_data.get('correct', None)
            self.votes = {i+1: set() for i in range(len(self.options))}
            self.singlevote = json_data.get('singlevote', True)

            # When the  file is read in, the timer specified there is used as a baseline. !makequiz and !startquiz
            # Can overwrite this value
            self.timer = json_data.get('timer', None)

            succesful = True

        except Exception:
            succesful = False

        return succesful, self

    def create_save_data(self):

        '''Function to store all data needed to reconstruct the class'''

        # Convert the vote sets to lists in order to be saved in a json file
        converted_votes = {key: list(data) for key,data in self.votes.items()}

        # Create the save dict
        toreturn = dict(
            name=self.name,
            messageid=self.message_id,
            channelid=self.channel_id,
            question=self.question,
            correct=self.correct_answer,
            options=self.options,
            owner=self.owner,
            votes=converted_votes,
            singlevote=self.singlevote,
            timer=self.timer,
            counted_votes={self.options[index]: len(self.votes[index])
                           for index in range(1, len(self.options) + 1)}
        )

        return toreturn

    def load_from_save_data(self, save_dict):

        '''Function for loading values into the class from a dictionary'''

        self.name = save_dict["name"]
        self.message_id = int(save_dict["messageid"])
        self.channel_id = int(save_dict["channelid"])
        self.question = save_dict["question"]

        self.options = save_dict["options"]
        self.options = {int(key): option for key,option in self.options.items()}

        self.correct_answer = None if not save_dict["correct"] else int(save_dict["correct"])
        self.owner = int(save_dict["owner"])

        self.votes = save_dict["votes"]
        self.votes = {int(key): set(data) for key,data in self.votes.items()}

        self.singlevote = save_dict.get("singlevote", True)
        self.timer = None if not save_dict["timer"] else int(save_dict["timer"])

        return self

    def generate_quiz_message(self):

        '''Function for generating all required parameters for a Discord message Embed to represent the quiz'''

        title = self.name
        question = self.question

        answer_options = "\n".join([f"{self.emoji_options[i]} ) {self.options[option]}"
                                    for i,option in enumerate(self.options)])

        informational_text = "Answer with the emoji's given below." + \
            ("Only your final answer counts!" if self.singlevote else "You can select multiple answers.")

        description = "\n\n".join([question, answer_options, informational_text])

        emojis = [self.emoji_options[i] for i in range(len(self.options))]

        return title, description, emojis

    def vote(self, voter_id, emoji):

        '''Function that handles user votes to the quiz and makes sure each user only has one final vote'''

        # If it's an invalid emoji, just return
        if not emoji in self.emoji_options:
            return

        # Delete the voter_id from all options
        if self.singlevote:
            for option in self.votes:
                if voter_id in self.votes[option]:
                    self.votes[option].remove(voter_id)
        # Cast the vote
        self.votes[self.emoji_options.index(emoji) + 1].add(voter_id)


    def create_histogram(self):

        """
        Function that creates a histogram to serve as quiz feedback, shows percentual distribution of votes.
        Returns a BytesIO() object that serves as an image file to pass into a Discord message.
        """

        # Create a BytesIO buffer to temporarily store the image
        image_buffer = io.BytesIO()
        image_buffer.name = f"{self.name.replace(' ','_')}_quiz_feedback.png"

        # Set the plot style to be easier to view in Discord
        plt.style.use('dark_background')

        # Get the distribution of votes in percentages
        individual_votes = np.array([len(self.votes[option]) for option in self.options])
        if np.sum(individual_votes) != 0:
            weighted_votes = individual_votes / np.sum(individual_votes) * 100
        else:
            weighted_votes = np.zeros(len(self.options)) * 100

        # Create a bar chart to represent the data
        figsize = np.array([6.4,4.8])*len(self.options)/9 if len(self.options) >= 9 else (6.4,4.8)
        plt.figure(figsize=figsize)
        barchart = plt.bar(np.array(range(1,len(self.options) + 1)), weighted_votes, width=0.4, color="r")
        plt.ylim((0,100))
        plt.gca().yaxis.set_major_formatter(PercentFormatter())
        plt.xticks(np.array(range(1, len(self.options) + 1)))
        plt.xlabel("Answers")
        plt.title(f"Total number of votes: {np.sum(individual_votes)}\n")

        # Color the correct answer green
        if self.correct_answer:
            barchart.patches[self.correct_answer - 1].set_facecolor("g")
        else:
            for patch in barchart.patches:
                patch.set_facecolor("b")

        # Show the values of the various bars in the bar chart above the bars
        for i, bar in enumerate(barchart):
            votes = individual_votes[i]
            plt.gca().text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1.2, f"{votes}",
                           ha='center', color='white', fontsize=12)

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

        self.save_filepath = self.datadir.joinpath("saved_quizzes.backupjson")

        # This dictionary contains all the currently active quizzes
        self.quizzes = {}
        self.last_started = ''
        self.dynamic_quiz_active = False
        self.load_quizzes()

    @commands.Cog.listener()
    async def on_message(self,ctx):

        # If the message is from the bot itself or there are no dynamic quizzes, don't execute this function
        if ctx.author.id == self.bot.user.id or not self.dynamic_quiz_active:
            return

        # If the previous check has been passed, but the message is not in the dynamic quiz channel, don't continue
        if ctx.channel.id != self.quizzes[
            list(filter(lambda k: self.quizzes[k].name == self.last_started, self.quizzes))[0]
        ].channel_id:
            return

        # If it wasn't a command, the message should still be deleted
        try:
            await ctx.delete()
        except:
            return

    def cog_unload(self):

        '''Function to handle unloading of the Poll Cog'''

        # Save all active quizzes before shutdown
        print('Unloading Poll Cog')
        self.save_quizzes()
        return super().cog_unload()

    def save_quizzes(self):

        '''Function to save a pickle object containing all the currently active quizzes'''

        save_dict = {message_id: self.quizzes[message_id].create_save_data() for message_id in self.quizzes}

        save_dict["last_started"] = self.last_started

        save_dict["dynamic_active"] = self.dynamic_quiz_active


        with open(self.save_filepath, 'w') as file:
            json.dump(save_dict,file)

    @commands.command("savequiz",aliases=("save-quiz","save_quiz","savequizzes","save-quizzes","save_quizzes"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def save_quiz(self,ctx):

        '''Save all currently active quizzes to disk.'''

        await ctx.message.delete()

        self.save_quizzes()
        await ctx.channel.send(f"<@{ctx.author.id}> Currently active quizzes saved!",
                               delete_after=20)

    def load_quizzes(self):
        '''Function to load the pickle object containing all the currently active quizzes'''

        # If it doesn't exist, there is nothing to load.
        if not self.save_filepath.exists():
            self.save_quizzes()
            return
        with open(self.save_filepath, 'r') as file:
            json_data = json.load(file)

        self.last_started = json_data.get("last_started", None)
        self.dynamic_quiz_active = json_data.get("dynamic_active", False)
        json_data.pop("last_started", None)
        json_data.pop("dynamic_active", None)

        self.quizzes = {int(message_id): Quiz(None,None).load_from_save_data(json_data[message_id])
                        for message_id in json_data}

        print(f"Quiz system loaded with following parameters:\n"
              f"- Active quizzes: {len(self.quizzes)}\n"
              f"- Last quiz started: {self.last_started}\n"
              f"- Dynamic quiz active: {self.dynamic_quiz_active}")

    @commands.command("quiz-status", aliases=("quizstatus", "quiz_status"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def get_quiz_system_status(self, ctx):
        await ctx.message.delete()
        status = \
            f"""
            ** Currently active quizzes: ** {len(self.quizzes)}
            ** Last started quiz: **        {self.last_started}
            ** Dynamic quiz active: **      {self.dynamic_quiz_active}            
            """
        embed = discord.Embed(title="Quiz system status", description=status, colour=0x25a52b)
        await ctx.message.channel.send(embed=embed, delete_after=20)


    @commands.command("startquiz", aliases=("start-quiz","start_quiz","quiz","beginquiz","begin-quiz",
                                            "begin_quiz","launchquiz","launch_quiz","launch-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def start_quiz(self, ctx, fname : str, timeout : int = None):

        '''
        Discord command to start a quiz.

        Arguments:
        - fname: The JSON file containing the quiz
        - timeout: Timeout in seconds for each question (optional)
        '''

        # Save the channel in which the message was sent
        quiz_channel = ctx.channel
        # Save the creator's id to privately send feedback after the quiz is finished
        quiz_creator = ctx.author.id

        # Delete the message containing the command
        await ctx.message.delete()

        # Add a .json extension if it is not present
        fname += ".json" if ".json" not in fname else ""

        quiz_filepath = self.datadir.joinpath(fname)

        # Check if the filename specified actually exists
        if not quiz_filepath.exists():
            await ctx.channel.send(
                f"<@{ctx.author.id}> The filename provided does not seem to exist, please check spelling and try again.",
                delete_after=20
            )
            return

        # Create the new quiz
        was_succesful, new_quiz = Quiz(quiz_filepath, quiz_creator).load_data()

        # Abort if the data reading has failed. If the bot has been properly configured, this means that the json
        # formatting is wrong.
        if not was_succesful:
            await ctx.channel.send(
                f"<@{ctx.author.id}> The json quiz file has been improperly formatted!",
                delete_after=20
            )
            return

        if timeout != None:
            timeout = int(timeout)
            new_quiz.timer = timeout if timeout not in (-1,0) else None


        # Create the message belonging to the quiz and give it a blue coloured embed
        title, description, emojis = new_quiz.generate_quiz_message()
        embed = discord.Embed(title=title, description=description, colour=0x3939cf)
        new_message = await quiz_channel.send(embed=embed)

        # Now attach this new message's id to the new quiz
        new_quiz.message_id = new_message.id
        new_quiz.channel_id = new_message.channel.id

        # Add the quiz to the internal dict
        self.quizzes[new_quiz.message_id] = new_quiz
        self.last_started = new_quiz.name

        # Add the appropriate reactions
        for em in emojis:
            await new_message.add_reaction(em)

        # If the quiz has a timer, activate it
        if new_quiz.timer:
            self.bot.loop.create_task(self.quiz_timer(new_quiz.timer,new_message))

    @commands.command("dynamic", aliases=("makedynamic", "make_dynamic", "make-dynamic", "dynamicquiz", "dynamic-quiz",
                                          "dynamic_quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def make_quiz_dynamic(self,ctx):

        """
        Turns the last activated quiz into a dynamic quiz.
        """

        # Turn on dynamic quiz mode
        if self.last_started:
            self.dynamic_quiz_active = True
        await ctx.message.delete()

    @commands.command("allow-multiple", aliases=("allowmult","allow_mult", "allow_multiple"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_allow_multiple(self, ctx):
        '''
            Turns the last activated quiz in a quiz where
            multiple answers are allowed per user.
        '''

        await ctx.message.delete()

        if self.last_started:
            last_quiz = self.quizzes[list(
                filter(lambda k: self.quizzes[k].name == self.last_started, self.quizzes))[0]]
            last_quiz.singlevote = False

            # Now generate a new quiz embed and react with the appropriate new reaction
            title, description, emojis = last_quiz.generate_quiz_message()
            original_message = await ctx.message.channel.fetch_message(last_quiz.message_id)
            original_embed = original_message.embeds[0].to_dict()
            original_embed["description"] = description
            await original_message.edit(embed=discord.Embed().from_dict(original_embed))

    @commands.command("add")
    @commands.guild_only()
    async def add_quiz_option(self, ctx, *args):

        """
        Add an option to a dynamic quiz.

        Arguments:
            - Option you want to add
        """

        await ctx.message.delete()
        # If there's no dynamic quiz active, don't continue
        if not self.dynamic_quiz_active:
            return

        addition = " ".join(args)

        last_quiz = self.quizzes[list(filter(lambda k: self.quizzes[k].name == self.last_started, self.quizzes))[0]]

        # That option is already in the quiz or the max amount of options has been reached
        if len(last_quiz.options) == len(last_quiz.emoji_options):
            return
        options = [option.lower() for option in last_quiz.options.values()]
        if addition.lower() in options:
            vote_index = options.index(addition.lower())
            last_quiz.vote(ctx.author.id, last_quiz.emoji_options[vote_index])
            return

        current_option_length = len(last_quiz.options)
        last_quiz.options[current_option_length + 1] = addition
        last_quiz.votes[current_option_length + 1] = set()

        last_quiz.vote(ctx.author.id, last_quiz.emoji_options[current_option_length])

        # Now generate a new quiz embed and react with the appropriate new reaction
        title, description, emojis = last_quiz.generate_quiz_message()
        original_message = await ctx.message.channel.fetch_message(last_quiz.message_id)
        original_embed = original_message.embeds[0].to_dict()
        original_embed["description"] = description
        await original_message.edit(embed=discord.Embed().from_dict(original_embed))
        await original_message.add_reaction(emojis[-1])



    @commands.command("finishquiz", aliases=("finish-quiz", "finish_quiz", "endquiz","end_quiz","end-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def finish_quiz(self,ctx,*args):
        """
        End a quiz and publish its results using a histogram.
        It sends the histogram to the channel where the quiz resides as well as the people who started
        and ended the quiz.

        Arguments:
            - quiz name (optional, last started quiz will be used if not provided)
        """
        # If this is the case, then this was not an internal function call and it was an actual command
        if not type(ctx) == int:
            # Save the author and channel for future reference
            author_id = ctx.author.id
            message_channel = ctx.channel

            # Delete the message containing the command
            await ctx.message.delete()

            quiz_name = " ".join(args) if args else self.last_started
            if not args:
                self.last_started = None

            try:
                quiz_to_finish = self.quizzes[list(filter(lambda k: self.quizzes[k].name == quiz_name, self.quizzes))[0]]
            except Exception:
                await ctx.channel.send(
                    f"<@{ctx.author.id}> That quiz does not exist, please check the spelling of the name you provided!",
                    delete_after=20
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

        # Get the original quiz message
        message = await message_channel.fetch_message(quiz_to_finish.message_id)

        # Clear the reactions and set the embed colour to green
        await message.clear_reactions()
        altered_embed = message.embeds[0].to_dict()
        altered_embed["color"] = 0x25a52b # Green
        # altered_embed.pop("footer")
        altered_embed = discord.Embed.from_dict(altered_embed)
        await message.edit(embed=altered_embed)

        # Get the recipients of the feedback chart
        channel = self.bot.get_channel(quiz_to_finish.channel_id)
        owner = self.bot.get_user(quiz_to_finish.owner)
        author = self.bot.get_user(author_id)

        # Send the feedback chart to the recipients
        for recipient in {channel, owner, author}:
            # Reset the buffer internal index to 0 again
            feedback_chart.seek(0)

            # Create the file object and embed again to avoid errors
            file_object = discord.File(feedback_chart, filename=feedback_chart.name)
            embed = discord.Embed(title=f"Feedback for {quiz_to_finish.name}", colour=0x25a52b)
            embed.set_image(url=f"attachment://{feedback_chart.name}")

            await recipient.send(embed=embed,file=file_object)

        # Remove the quiz from the internal dictionary
        self.quizzes.pop(quiz_to_finish.message_id)

        # If this was a dynamic quiz, disable message deletion again
        self.dynamic_quiz_active = False

    @commands.command("intermediate_results", aliases=("intermediateresults", "intermediate-results", "intermediate"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def quiz_intermediate_results(self,ctx, public: str = "True", quiz_name: str = None):

        '''
        Function to obtain intermediate results of a quiz.
        Arguments:
            - public [defaults to True] (optional)
            - quiz name (optional, last started quiz will be used if not provided)
        Note:
            public parameter must also be specified if a quiz name is passed as argument
        '''

        if not quiz_name:
            quiz_name = self.last_started

        public = public.lower() in ("true", "yes", "1", "public")

        await ctx.message.delete()

        try:
            quiz = self.quizzes[list(filter(lambda k: self.quizzes[k].name == quiz_name, self.quizzes))[0]]

        except Exception:
            await ctx.channel.send(
                f"<@{ctx.author.id}> That quiz does not exist, please check the spelling of the name you provided!",
                delete_after=20
            )
            return

        # Get the current feedback chart
        quiz_chart = quiz.create_histogram()

        recipients = [self.bot.get_channel(quiz.channel_id)] * public + [ctx.message.author]

        for recipient in recipients:
            # Reset the bytesIO index to 0
            quiz_chart.seek(0)

            # Create the embed
            file_object = discord.File(quiz_chart, filename=quiz_chart.name)
            embed = discord.Embed(title=f"Intermediate feedback for {quiz.name}", colour=0x3939cf)
            embed.set_image(url=f"attachment://{quiz_chart.name}")

            await recipient.send(embed=embed, file=file_object, delete_after=50)


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

        '''
        Function to create a quiz. Two different methods available:
        - Method 1:
            Provide details of quiz through pre-made json file.

            Arguments:
                - json filename [used for storing the file to disk]
            Attachments:
                - json file containing all quiz details

        - Method 2:
            Provide details of quiz in message directly

            Arguments:
                - quiz filename [used for storing the quiz file to disk]
                - quiz name [used for naming the quiz and manipulating it once activated]
                - question
                - options [options must be given in one argument, separated by semicolon (;)]
                - correct answer (optional)
                - timer [specified using the following syntax: timer=xx where xx is the value in seconds] (optional)
        '''

        if len(args) == 0:
            await ctx.channel.send(f"<@{ctx.author.id}> No arguments were given!",
                                   delete_after=20)
            await ctx.message.delete()
            return

        # If a file has been attached, this means the quiz is attached in a json file format
        if len(ctx.message.attachments) > 0:
            # In this case, the command usage dictates that the argument is the filename that should be used
            # to save the json file.
            file_name = " ".join(args)
            file_name += ".json" if ".json" not in file_name else ""
            await ctx.message.attachments[0].save(self.datadir.joinpath(file_name), use_cached=False, seek_begin=True)
            await ctx.message.delete()
            return

        # If not, the json data must be given as an argument
        if not len(args) >= 4:
            await ctx.channel.send(f"<@{ctx.author.id}> Incorrect usage of command! Either attach the json file to "
                                   f"the message and provide the filename as argument or provide filename, quiz name, "
                                   f"question, answers and, if applicable, the correct response as separate arguments.",
                                   delete_after=20)
            await ctx.message.delete()
            return
        timer_value = ''
        # A timer value was added, which needs to be extracted now
        if "timer=" in args[-1]:
            timer_value = f', "timer":{args[-1].lower().strip("timer=")}'
            args = args[:-1]

        file_name = args[0] + (".json" if ".json" not in args[0] else "")
        quiz_name = args[1]
        question = args[2]
        correct = f', "correct": {args[-1]}' if len(args) == 5 else ''
        options_parsed = args[3].split(";")
        options_parsed = ','.join([f'"{opt}"' for opt in options_parsed])

        json_string = f'{{"name": "{quiz_name}", "question": "{question}",' \
                      f' "options": [{options_parsed}]{correct}{timer_value}}}'

        with open(self.datadir.joinpath(file_name), 'w') as file:
            file.write(json_string)

        await ctx.message.delete()

    @commands.command("directquiz", aliases=("direct-quiz", "direct_quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def direct_quiz(self,ctx, *args):

        """
        Function to create and start a quiz directly without writing it to a json file. Syntax is comparable to
        the !makequiz command with all arguments given in the message itself (method 2), no attachments.
        The filename must be left out as this quiz is not saved to disk. See !help makequiz for details about its usage.
        """

        if not len(args) >= 3:
            await ctx.channel.send(f"<@{ctx.author.id}> Incorrect usage of command! Provide quiz name, "
                                   f"question, answers and, if applicable, the correct response and timer value"
                                   f"as separate arguments.",
                                   delete_after=20)
            await ctx.message.delete()
            return

        timer_value = None
        # A timer value was added, which needs to be extracted now

        if "timer=" in args[-1]:
            timer_value = int(args[-1].lower().strip("timer="))
            args = args[:-1]

        # Extract all the other options
        quiz_name = args[0]
        question = args[1]
        correct = int(args[-1]) if len(args) == 4 else None
        options_parsed = args[2].split(";")

        quiz_channel = ctx.message.channel

        # Instantiate a Quiz object and populate it with the relevant variables
        newquiz = Quiz(None, ctx.author.id)
        newquiz.name = quiz_name
        newquiz.question = question
        newquiz.options = {i+1: str(option) for i,option in enumerate(options_parsed)}
        newquiz.votes = {i+1: set() for i in range(len(options_parsed))}
        newquiz.correct_answer = correct
        newquiz.timer = timer_value


        # Create the message belonging to the quiz and give it a blue coloured embed
        title, description, emojis = newquiz.generate_quiz_message()
        embed = discord.Embed(title=title, description=description, colour=0x3939cf)
        new_message = await quiz_channel.send(embed=embed)

        # Now attach this new message's id to the new quiz
        newquiz.message_id = new_message.id
        newquiz.channel_id = new_message.channel.id

        # Add the quiz to the internal dict
        self.quizzes[newquiz.message_id] = newquiz
        self.last_started = newquiz.name

        # Add the appropriate reactions
        for em in emojis:
            await new_message.add_reaction(em)

        # If the quiz has a timer, activate it
        if newquiz.timer:
            self.bot.loop.create_task(self.quiz_timer(newquiz.timer, new_message))



        await ctx.message.delete()




    @commands.command("viewquiz", aliases=("viewquizzes", "view_quizzes", "view_quiz", "view-quizzes", "view-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def view_quizzes(self,ctx):
        ''' List all stored json files as well as all active quizzes. '''

        json_files = [path.name for path in list(self.datadir.rglob("*.json"))]
        currently_active = [self.quizzes[message_id].name for message_id in self.quizzes]
        to_send = "Quiz JSON files: \n- "*(len(json_files)>0) + "\n- ".join(json_files) + "\n\n" + \
            "Currently active quizzes: \n- "*(len(currently_active) > 0) + "\n- ".join(currently_active)


        # Check if the string is empty
        if len(to_send.strip()) == 0:
            await ctx.channel.send(f"<@{ctx.author.id}> There are no json files stored and no quizzes active.",
                                   delete_after=20)
        else:
            embed = discord.Embed(title="Quiz JSON files and active quizzes", description=to_send, colour=0x25a52b)
            await ctx.channel.send(embed=embed, delete_after=30)
        await ctx.message.delete()

    @commands.command("inspectquiz", aliases=("inspect_quiz", "inspect-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def inspect_quiz_json(self,ctx,*args):

        '''
        Send the specified quiz json file to the user via a direct message.

        Arguments:
            - quiz filename
        '''

        filename = " ".join(args)
        filename += ".json" if ".json" not in filename else ""

        filepath = self.datadir.joinpath(filename)
        if not filepath.exists():
            await ctx.channel.send(f"<@{ctx.author.id}> That file does not exist!",
                                   delete_after=20)
        else:
            await ctx.channel.send(f"<@{ctx.author.id}> File will be sent via private message.",
                                   delete_after=20)
            await self.bot.get_user(ctx.author.id).send(f"<@{ctx.author.id}> Here is the file that you requested.",
                                                        file=discord.File(filepath))
        await ctx.message.delete()

    @commands.command("delquiz", aliases=("delete-quiz", "deletequiz", "delete_quiz", "removequiz", "remove-quiz", "remove_quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def remove_quiz(self,ctx,*args):

        '''
        Function to remove a stored json file.

        Arguments:
            - quiz filename
        '''

        filename = " ".join(args)
        filename += ".json" if ".json" not in filename else ""
        filepath = self.datadir.joinpath(filename)
        if not filepath.exists():
            await ctx.channel.send(f"<@{ctx.author.id}> That file does not exist!",
                                   delete_after=20)
        else:
            filepath.unlink()
            await ctx.channel.send(f"<@{ctx.author.id}> File deleted!",
                                   delete_after=20)
        await ctx.message.delete()


    async def quiz_timer(self, timer_duration, message_object):

        '''Function to dynamically update the timer value on a quiz and automatically end it'''

        timer = timer_duration
        t = lambda x: f"{0 if x//60 < 10 else ''}{x // 60}:{0 if x % 60 < 10 else ''}{x % 60}{0 if x % 60 == 0 else ''}"


        while timer > 0:
            new_timer_value = f"Time left: {t(timer)}"
            embed = (await message_object.channel.fetch_message(message_object.id)).embeds[0]
            embed.set_footer(text=new_timer_value)
            await message_object.edit(embed=embed)
            await asyncio.sleep(1)
            timer -= 1

        await self.finish_quiz(message_object.id)
