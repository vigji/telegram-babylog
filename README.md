# `telegram-babylog`

As baby logging seems to be mostly handled by over-proced and ads-ridden apps with little access to raw data, this is a simple, minimal solution using Telegram and GoogleDrive.


### Requirements
The project has been tested with the following:
- `python == 3.10.0`
- `python-telegram-bot[job-queue]==21.1.1`
- `asynchio`
- `google-api-python-client`
- `google-auth`


## Organization of the project
The project is organized as follows:
 - `gdrive_log.py`: Contains a bunch of functions to set up and interact with the remote Google Drive storage.
 - `csv_logger.py`: Contains a class to handle the log of the baby data in a CSV file that can be backed up to Google Drive.
 - `main.py`: Contains the main bot class and the handlers for the different commands.

## Running the bot
1. Create a new bot using the BotFather on Telegram.
2. Create a new Google Cloud project and enable the Google Drive API.
3. Configure the `defaults.py` file with the necessary credentials from Telegram and Google.

## Deployment
For the deployment, I used a headless RasPi 0 with a cron job to run the bot at startup.

