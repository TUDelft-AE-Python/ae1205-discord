import discord
from discord.ext import commands
import json
import emoji # Library used for handling emoji codes
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np
import io # For generating discord .png
import os # For checking if quiz file exists

# Define a shorthand for obtaining the emoji belonging to a :emoji: string
get_emoji = lambda em: emoji.emojize(em, use_aliases=True)


# Global settings for quizzes
quiz_directory = "./quizzes/"

class Quiz:
    def __init__(self,name,json_file, owner):
        self.name = name
        self.filename = json_file
        self.owner = owner

        self.message_id = None

        self.question = ""
        self.correct_answer = 0
        self.options = {}

        self.votes = {}

        self.load_data()

        self.emoji_options = [get_emoji(em) for em in
                              (":one:",":two:",":three:",":four:",":five:",":six:",":seven:",":eight:",":nine:")]

    def load_data(self):
        with open(self.filename, "r") as file:
            json_data = json.load(file)

        self.question = json_data["question"]
        self.options = {i: option for i,option in enumerate(json_data["options"])}
        self.correct_answer = json_data["correct"]
        self.votes = {i: 0 for i in range(len(self.options))}

    def generate_quiz_message(self):
        title = self.name
        question = self.question

        answer_options = "\n".join(["{}) {}".format(i+1, option) for i,option in enumerate(self.options)])

        informational_text = "Answer with the emoji's given below. Only your final answer counts!"

        description = "\n\n".join([question, answer_options, informational_text])

        emojis = [self.emoji_options[i] for i in range(len(self.options))]

        return title, description, emojis

    def vote(self, voter_id, emoji):
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

        # Create a BytesIO buffer to temporarily store the image
        image_buffer = io.BytesIO()
        image_buffer.name = "{}_quiz_feedback.png".format(self.name)

        # Create the histogram bins for proper plotting
        bins = np.array([i for i in range(1, len(self.options) + 2)]) - 0.5

        # Get the weight of the votes
        individual_votes = np.array([len(self.votes[option]) for option in self.options])
        weighted_votes = individual_votes/np.sum(individual_votes)

        # Draw histogram
        n, bins, patches = plt.hist(
            [i for i in range(1,len(self.options) + 1, 1)],
             bins=bins,
             rwidth=0.75,
             weights=weighted_votes
        )

        # Color correct patch green
        patches[self.correct_answer - 1].set_facecolor('g')

        # Configure grid and ticks to show percentage histogram of the answers
        plt.gca().yaxis.set_major_formatter(PercentFormatter(1))
        plt.grid(axis='y')
        plt.xticks([i for i in range(1, len(self.options) + 1)])


        # Save figure to image buffer
        plt.savefig(image_buffer, format="png", bbox_inches="tight")
        plt.close()

        # Reset the buffer internal index to the beginning
        image_buffer.seek(0)

        return image_buffer





class Poll(commands.Cog):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot

        self.quizzes = {}

    @commands.command("makequiz", aliases=("make-quiz","make_quiz","quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def create_quiz(self,ctx,*args):

        # Save the channel in which the message was sent
        quiz_channel = ctx.channel
        # Save the creator's id to privately send feedback after the quiz is finished
        quiz_creator = ctx.author.id

        # Delete the message containing the command
        await ctx.message.delete()

        try:
            quiz_filename = args[0]
            quiz_name = " ".join(args[1:])
        except Exception:
            await ctx.channel.send(
                "<@{}> Command used incorrectly! Please provide the filename first, then the quiz name".format(
                    ctx.author.id
                ),
                delete_after=3
            )
            return

        # Add a .json extension if it is not present
        if not ".json" in quiz_filename:
            quiz_filename += ".json"

        # Check if the filename specified actually exists
        if not os.path.exists(quiz_directory+quiz_filename):
            await ctx.channel.send(
                "<@{}> The filename provided does not seem to exist, please check spelling and try again.".format(
                    ctx.author.id
                ),
                delete_after=3
            )
            return

        # Create the new quiz
        new_quiz = Quiz(quiz_name,quiz_filename,quiz_creator)
        self.quizzes.append(new_quiz)

        # Create the message belonging to the quiz and give it a nice green coloured embed
        title, description, emojis = new_quiz.generate_quiz_message()
        embed = discord.Embed(title=title, description=description, colour=0x41f109)
        new_message = await quiz_channel.send(embed=embed)

        # Now attach this new message's id to the new quiz
        new_quiz.message_id = new_message.id

    @commands.command("finishquiz", aliases=("finish-quiz", "finish_quiz", "endquiz","end_quiz","end-quiz"))
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def finish_quiz(self,ctx,*args):
        # Save the author and channel for future reference
        author_id = ctx.author.id
        message_channel = ctx.channel

        # Delete the message containing the command
        await ctx.message.delete()

        quiz_name = " ".join(args)
        try:
            quiz_to_finish = self.quizzes[quiz_name]
        except Exception:
            await ctx.channel.send(
                "<@{}> That quiz does not exist, please check the spelling of the name you provided!".format(
                    ctx.author.id
                ),
                delete_after=3
            )
            return

        feedback_chart = quiz_to_finish.create_histogram()

        # Send the feedback chart to the person who created the quiz and the person who ended it
        for user_id in (author_id, quiz_to_finish.owner):
            await message_channel.guid.get_member(user_id).send("Feedback graph for {}!".format(quiz_to_finish.name),
                                                                file=discord.File(feedback_chart))
        # Remove the quiz from the internal dictionary
        self.quizzes.pop(quiz_name)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self,ctx):
        message_id = ctx.message_id
        if not message_id in self.quizzes:
            return
        # The RawReactionEvent object only contains id's, so these need to be converted to usable
        # discord Channel, Message and Member objects in order to delete the received reaction
        reaction_channel = self.bot.get_channel(ctx.channel_id)
        reaction_message = await reaction_channel.fetch_message(message_id)
        reaction_member = reaction_channel.guild.get_member(ctx.user_id)
        await reaction_message.remove_reaction(ctx.emoji, reaction_member)

        # Call the vote command. If an invalid emoji has been used, this will do nothing
        self.quizzes[message_id].vote(reaction_member.id, str(ctx.emoji))








