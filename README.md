
# ARK Server Discord Bot

A powerful Discord bot for managing ARK: Survival Evolved servers remotely.

## Features

- Server management (start/stop/restart/status)
- Player management (list/kick/ban/unban)
- World commands (save/set time/destroy wild dinos)
- Broadcast messages to players
- Check for updates
- Run custom RCON commands
- Automatic server status monitoring

## Setup Instructions

1. **Create a .env file with the following credentials:**
   - Copy `.env.example` to `.env`
   - Add your Discord bot token
   - Add your VPS SSH connection details

2. **Install dependencies:**
   - Python 3.11+
   - discord.py
   - paramiko
   - python-dotenv

3. **Start the bot:**
   - Run `python ark_discord_bot.py`
   - The bot will connect to your VPS via SSH
   - The bot will automatically register slash commands

## Available Commands

- `/status <server>` - Get detailed status
- `/start <server>` - Start server
- `/stop <server>` - Stop server
- `/restart <server>` - Restart server
- `/players <server>` - List online players
- `/broadcast <server> <message>` - Send message to all players
- `/ban <server> <player>` - Ban a player
- `/kick <server> <player>` - Kick a player
- `/unban <server> <player>` - Unban a player
- `/backup <server>` - Create a server backup
- `/update <server>` - Update the server
- `/saveworld <server>` - Save the world
- `/destroywilddinos <server>` - Remove all wild creatures
- `/settime <server> <HH:MM>` - Set in-game time
- `/getchat <server>` - Get recent chat logs
- `/rcon <server> <command>` - Run custom RCON command

## Deployment

This bot is designed to run on Replit. To deploy:

1. Click the "Deploy" button
2. Choose "Scheduled Deployments" or "Reserved VM Deployments"
3. Follow the setup instructions

## Requirements

Your ARK server must have arkmanager installed and configured.
