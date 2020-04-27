''' Main script to start EduBot. '''
import os
from edubot import EduBot


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    bot = EduBot()
    bot.run(TOKEN)
