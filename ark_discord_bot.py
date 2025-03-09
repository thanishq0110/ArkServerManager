
import discord
import os
import asyncio
import paramiko
import re
from discord.ext import commands, tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
VPS_HOST = os.getenv("VPS_HOST")
VPS_USERNAME = os.getenv("VPS_USERNAME")
VPS_PASSWORD = os.getenv("VPS_PASSWORD")

# Validate environment variables
if not TOKEN:
    raise ValueError("Bot token is missing! Set DISCORD_BOT_TOKEN in your .env file.")
if not all([VPS_HOST, VPS_USERNAME, VPS_PASSWORD]):
    raise ValueError("VPS credentials are missing! Set VPS_HOST, VPS_USERNAME, and VPS_PASSWORD in your .env file.")

# Available server instances
SERVERS = ["ragnarok", "fjordur", "main", "all"]

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

class SSHClient:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("📡 SSH client initialized")
        self.connected = False

    async def connect(self) -> bool:
        """Establish SSH connection"""
        try:
            print(f"🔄 Attempting SSH connection to {VPS_HOST}...")
            self.ssh.connect(
                hostname=VPS_HOST,
                username=VPS_USERNAME,
                password=VPS_PASSWORD,
                timeout=30
            )
            self.connected = True
            print("✅ SSH connection successful")
            return True
        except Exception as e:
            print(f"❌ SSH connection error: {e}")
            return False

    async def execute_command(self, command: str) -> tuple[str, bool]:
        """Execute command via SSH"""
        try:
            if not self.ssh.get_transport() or not self.ssh.get_transport().is_active():
                if not await self.connect():
                    return "Failed to connect to VPS", False

            print(f"📤 Executing command: {command}")
            stdin, stdout, stderr = self.ssh.exec_command(command, timeout=60)
            output = stdout.read().decode()
            error = stderr.read().decode()

            if error and not output:
                print(f"⚠️ Command error: {error}")
                return error, False

            print("✅ Command executed successfully")
            return output or "Command executed successfully", True

        except Exception as e:
            print(f"❌ Command execution error: {e}")
            return str(e), False

    def close(self):
        """Close SSH connection"""
        if self.connected:
            self.ssh.close()
            self.connected = False
            print("📡 SSH connection closed")

ssh_client = SSHClient()

async def execute_ark_command(command: str, server_name: str) -> tuple[str, discord.Color]:
    """Execute ARK server command and return formatted response"""
    # Format command based on type
    if command == "listplayers":
        cmd = f'arkmanager rconcmd "ListPlayers" @{server_name}'
    elif command.startswith("rconcmd"):
        # Handle RCON commands by ensuring @server is at the end
        rcon_cmd = command.replace('rconcmd ', '')
        # Ensure the command is wrapped in quotes if not already
        if not (rcon_cmd.startswith('"') and rcon_cmd.endswith('"')):
            rcon_cmd = f"\"{rcon_cmd}\""
        cmd = f"arkmanager rconcmd {rcon_cmd} @{server_name}"
    elif command.startswith("broadcast"):
        # Handle broadcast command
        message = command.replace("broadcast ", "")
        cmd = f'arkmanager rconcmd "Broadcast {message}" @{server_name}'
    else:
        # Regular arkmanager commands
        cmd = f"arkmanager {command} @{server_name}"

    print(f"📤 Executing command: {cmd}")
    output, success = await ssh_client.execute_command(cmd)

    # Clean ANSI color codes and whitespace
    output = re.sub(r'\x1b\[[0-9;]*m', '', output).strip()

    if not success:
        return output, discord.Color.red()

    # Format empty player list response
    if command == "listplayers" and not output.strip():
        output = "No players currently online"

    # Add command execution confirmation if output is empty
    if not output:
        output = f"Command executed successfully: {cmd}"

    return output, discord.Color.green() if success else discord.Color.red()

async def send_response(interaction: discord.Interaction, title: str, output: str, color: discord.Color):
    """Send formatted response as Discord embed"""
    embed = discord.Embed(
        title=f"**{title}**",
        color=color,
        timestamp=datetime.utcnow()
    )

    if output:
        # Split long outputs into chunks
        if len(output) > 1024:
            chunks = [output[i:i+1024] for i in range(0, len(output), 1024)]
            for i, chunk in enumerate(chunks, 1):
                embed.add_field(
                    name=f"Output (Part {i}/{len(chunks)})",
                    value=f"```{chunk}```",
                    inline=False
                )
        else:
            embed.add_field(name="Output", value=f"```{output}```", inline=False)

    embed.set_footer(text=f"Requested by {interaction.user.name}")
    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")
    await interaction.followup.send(embed=embed)

# Core Commands
@bot.tree.command(name="status", description="Get ARK server status")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def server_status(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("status", server)
    await send_response(interaction, f"🖥️ Server Status: {server}", output, color)

@bot.tree.command(name="start", description="Start the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def start_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("start", server)
    await send_response(interaction, f"🚀 Starting Server: {server}", output, color)

@bot.tree.command(name="stop", description="Stop the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def stop_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("stop", server)
    await send_response(interaction, f"🛑 Stopping Server: {server}", output, color)

@bot.tree.command(name="restart", description="Restart the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def restart_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("restart", server)
    await send_response(interaction, f"🔄 Restarting Server: {server}", output, color)

@bot.tree.command(name="players", description="List online players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def list_players(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("listplayers", server)
    await send_response(interaction, f"👥 Online Players: {server}", output, color)

@bot.tree.command(name="broadcast", description="Broadcast message to all players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def broadcast_message(interaction: discord.Interaction, server: str, message: str):
    await interaction.response.defer()
    output, color = await execute_ark_command(f"broadcast {message}", server)
    await send_response(interaction, f"📢 Broadcast Message: {server}", output, color)

@bot.tree.command(name="backup", description="Create a backup of the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def backup_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("backup", server)
    await send_response(interaction, f"💾 Server Backup: {server}", output, color)

@bot.tree.command(name="update", description="Update the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def update_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("update", server)
    await send_response(interaction, f"🔧 Server Update: {server}", output, color)

@bot.tree.command(name="checkupdate", description="Check for game or mod updates")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def check_update(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("checkupdate", server)
    await send_response(interaction, f"🔍 Check Updates: {server}", output, color)

@bot.tree.command(name="checkmodupdate", description="Check for mod updates")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def check_mod_update(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("checkmodupdate", server)
    await send_response(interaction, f"🧩 Check Mod Updates: {server}", output, color)

@bot.tree.command(name="ban", description="Ban a player from the server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def ban_player(interaction: discord.Interaction, server: str, player_name: str):
    await interaction.response.defer()
    output, color = await execute_ark_command(f"rconcmd \"BanPlayer {player_name}\"", server)
    await send_response(interaction, f"🚫 Ban Player: {player_name}", output, color)

@bot.tree.command(name="kick", description="Kick a player from the server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def kick_player(interaction: discord.Interaction, server: str, player_name: str):
    await interaction.response.defer()
    output, color = await execute_ark_command(f"rconcmd \"KickPlayer {player_name}\"", server)
    await send_response(interaction, f"👢 Kick Player: {player_name}", output, color)

@bot.tree.command(name="unban", description="Unban a player from the server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def unban_player(interaction: discord.Interaction, server: str, player_name: str):
    await interaction.response.defer()
    output, color = await execute_ark_command(f"rconcmd \"UnbanPlayer {player_name}\"", server)
    await send_response(interaction, f"✅ Unban Player: {player_name}", output, color)

@bot.tree.command(name="saveworld", description="Save the current world state")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def save_world(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("rconcmd \"SaveWorld\"", server)
    await send_response(interaction, f"💾 Save World: {server}", output, color)

@bot.tree.command(name="destroywilddinos", description="Remove all wild creatures from the map")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def destroy_wild_dinos(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("rconcmd \"DestroyWildDinos\"", server)
    await send_response(interaction, f"🦖 Destroy Wild Dinos: {server}", output, color)

@bot.tree.command(name="settime", description="Set the in-game time (HH:MM format)")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def set_time(interaction: discord.Interaction, server: str, time: str):
    if not re.match(r"^\d{1,2}:\d{2}$", time):
        await interaction.response.send_message("⚠️ Invalid time format. Please use HH:MM format (e.g., 14:30)", ephemeral=True)
        return
    
    await interaction.response.defer()
    output, color = await execute_ark_command(f"rconcmd \"SetTimeOfDay {time}\"", server)
    await send_response(interaction, f"🕒 Set Time: {time}", output, color)

@bot.tree.command(name="getchat", description="Get recent chat logs from the server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def get_chat(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("rconcmd \"GetChat\"", server)
    await send_response(interaction, f"💬 Chat Logs: {server}", output, color)

@bot.tree.command(name="getlog", description="Get recent game logs from the server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def get_game_log(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("rconcmd \"GetGameLog\"", server)
    await send_response(interaction, f"📋 Game Logs: {server}", output, color)

@bot.tree.command(name="showmotd", description="Show the Message of the Day")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def show_motd(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, color = await execute_ark_command("rconcmd \"ShowMessageOfTheDay\"", server)
    await send_response(interaction, f"📣 Message of the Day: {server}", output, color)

@bot.tree.command(name="rcon", description="Send a custom RCON command to the server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def rcon_command(interaction: discord.Interaction, server: str, command: str):
    await interaction.response.defer()
    output, color = await execute_ark_command(f"rconcmd \"{command}\"", server)
    await send_response(interaction, f"🔧 RCON Command: {server}", output, color)

@bot.tree.command(name="help", description="Show available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎮 ARK Server Bot Commands",
        description="Here are the commands you can use:",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    
    # Server Management
    embed.add_field(
        name="🖥️ Server Management",
        value="```\n/status <server> - Check server status\n"
              "/start <server> - Start server\n"
              "/stop <server> - Stop server\n"
              "/restart <server> - Restart server\n"
              "/backup <server> - Create backup\n"
              "/update <server> - Update server\n"
              "/checkupdate <server> - Check for updates\n"
              "/checkmodupdate <server> - Check for mod updates```",
        inline=False
    )
    
    # Player Management
    embed.add_field(
        name="👥 Player Management",
        value="```\n/players <server> - List online players\n"
              "/ban <server> <player> - Ban player\n"
              "/kick <server> <player> - Kick player\n"
              "/unban <server> <player> - Unban player\n"
              "/broadcast <server> <message> - Send message to all players```",
        inline=False
    )
    
    # World Management
    embed.add_field(
        name="🌍 World Management",
        value="```\n/saveworld <server> - Save world\n"
              "/destroywilddinos <server> - Destroy wild dinos\n"
              "/settime <server> <HH:MM> - Set in-game time```",
        inline=False
    )
    
    # Information Commands
    embed.add_field(
        name="ℹ️ Information Commands",
        value="```\n/getchat <server> - Show recent chat\n"
              "/getlog <server> - Show game log\n"
              "/showmotd <server> - Show Message of the Day```",
        inline=False
    )
    
    # Advanced
    embed.add_field(
        name="🔧 Advanced",
        value="```\n/rcon <server> <command> - Send custom RCON command\n"
              "/help - Show this help message```",
        inline=False
    )
    
    embed.set_footer(text=f"Requested by {interaction.user.name}")
    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")
    
    await interaction.response.send_message(embed=embed)

@tasks.loop(minutes=5)
async def check_server_status():
    try:
        servers = {}
        for server in [s for s in SERVERS if s != "all"]:
            output, _ = await execute_ark_command("status", server)
            
            # Extract status from output
            running = False
            players = 0
            
            if "Server running: Yes" in output:
                running = True
            
            # Extract player count
            match = re.search(r"Players: (\d+)", output)
            if match:
                players = int(match.group(1))
            
            servers[server] = {"running": running, "players": players}
        
        # Update bot status
        total_players = sum(info["players"] for info in servers.values() if info["running"])
        online_servers = sum(1 for info in servers.values() if info["running"])
        
        status_message = f"🎮 {total_players} players on {online_servers} servers" if online_servers > 0 else "❌ No servers online"
        await bot.change_presence(activity=discord.Game(name=status_message))
        
    except Exception as e:
        print(f"❌ Error in status check: {e}")
        await bot.change_presence(activity=discord.Game(name="⚠️ Status check error"))

@bot.event
async def on_ready():
    """Bot startup event"""
    print(f"✅ {bot.user} is now online!")
    if await ssh_client.connect():
        print("✅ Successfully connected to VPS!")
        output, _ = await execute_ark_command("--version", "all")
        if "arkmanager not found" in (output or "").lower():
            print("⚠️ arkmanager needs to be installed")
        else:
            print("✅ arkmanager is installed and ready")
    else:
        print("❌ Failed to connect to VPS!")

    await bot.tree.sync()
    check_server_status.start()

# Start the bot
if __name__ == "__main__":
    bot.run(TOKEN)
