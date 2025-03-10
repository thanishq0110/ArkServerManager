# ARK Server Discord Bot

A Discord bot for managing ARK: Survival Evolved servers using slash commands.

## Prerequisites

1. A VPS with SSH access where your ARK server is running
2. Python 3.7+ installed on your VPS
3. Discord Bot Token (from Discord Developer Portal)

## Installation

1. Clone this repository to your VPS
2. Install required packages:
```bash
pip install discord.py python-dotenv paramiko
```

3. Create a `.env` file with your configuration:
```env
# Discord Bot Token
DISCORD_BOT_TOKEN=your_token_here

# VPS Configuration
VPS_HOST=your_vps_ip_here
VPS_USERNAME=your_vps_username_here
VPS_PASSWORD=your_vps_password_here
```

4. The bot will automatically install arkmanager if it's not found on your VPS.

## Available Commands

- `/start [server]` - Start the ARK server
- `/stop [server]` - Stop the ARK server
- `/restart [server]` - Restart the ARK server
- `/status [server]` - Get server status
- `/players [server]` - List online players
- `/broadcast [server] [message]` - Broadcast a message
- `/backup [server]` - Create a server backup
- `/update [server]` - Update server and mods
- `/rcon [server] [command]` - Execute RCON command

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
2. Install arkmanager if not present
3. Execute commands remotely
4. Update its status with player count every 2 minutes