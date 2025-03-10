
# ARK Server Discord Bot

A Discord bot for managing ARK: Survival Evolved servers using slash commands.

## Prerequisites

1. A VPS with SSH access where your ARK server is running
2. Python 3.7+ installed on your local machine
3. Discord Bot Token (from Discord Developer Portal)
4. ARKmanager installed on your VPS

## Installation

1. Clone this repository to your local machine
2. Install required packages:
```bash
pip install discord-py>=2.5.2 paramiko>=3.5.1 python-dotenv>=1.0.1
```

Alternatively, if you're using pip:
```bash
pip install discord.py python-dotenv paramiko
```

3. Create a `.env` file with your configuration (use .env.example as a template):
```env
# Discord Bot Token
DISCORD_BOT_TOKEN=your_token_here

# VPS Configuration
VPS_HOST=your_vps_ip_here
VPS_USERNAME=your_vps_username_here
VPS_PASSWORD=your_vps_password_here
```

## Available Commands

All commands use Discord's slash command system:

- `/status [server]` - Get ARK server status
- `/start [server]` - Start the ARK server
- `/stop [server]` - Stop the ARK server
- `/players [server]` - List online players
- `/broadcast [server] [message]` - Broadcast a message to all players
- `/rcon [server] [command]` - Execute RCON command (supports various sub-commands)

### RCON Sub-commands

The `/rcon` command supports various ARK server management functions:

**Player Management:**
- ListPlayers - Show online players
- KickPlayer - Kick a player
- BanPlayer - Ban a player
- UnbanPlayer - Unban a player

**World Management:**
- SaveWorld - Save the current world
- DestroyWildDinos - Remove all wild creatures
- SetTimeOfDay - Set world time

**Server Control:**
- Broadcast - Send message to all players
- ServerChat - Send message as SERVER

**Information:**
- GetChat - Show recent chat
- GetGameLog - Show game log
- ShowMessageOfTheDay - Show MOTD

## Server Instances
Available server instances:
- ragnarok
- fjordur
- main
- all

## Running the Bot

```bash
python ark_discord_bot.py
```

The bot will automatically:
1. Connect to your VPS using SSH
2. Check for arkmanager installation
3. Execute commands remotely
4. Provide formatted responses as Discord embeds
