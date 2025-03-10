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

@bot.tree.command(name="rcon", description="Send RCON command to server (use without command to see help)")
@app_commands.choices(
    server=[app_commands.Choice(name=s, value=s) for s in SERVERS],
    command=[
        # Player Management
        app_commands.Choice(name='"ListPlayers" - Show online players', value="\"ListPlayers\""),
        app_commands.Choice(name='"KickPlayer" - Kick a player', value="\"KickPlayer\""),
        app_commands.Choice(name='"BanPlayer" - Ban a player', value="\"BanPlayer\""),
        app_commands.Choice(name='"UnbanPlayer" - Unban a player', value="\"UnbanPlayer\""),
        # World Management
        app_commands.Choice(name='"SaveWorld" - Save the current world', value="\"SaveWorld\""),
        app_commands.Choice(name='"DestroyWildDinos" - Remove all wild creatures', value="\"DestroyWildDinos\""),
        app_commands.Choice(name='"SetTimeOfDay" - Set world time', value="\"SetTimeOfDay\""),
        # Server Control
        app_commands.Choice(name='"Broadcast" - Send message to all', value="\"Broadcast\""),
        app_commands.Choice(name='"ServerChat" - Send as SERVER', value="\"ServerChat\""),
        # Information
        app_commands.Choice(name='"GetChat" - Show recent chat', value="\"GetChat\""),
        app_commands.Choice(name='"GetGameLog" - Show game log', value="\"GetGameLog\""),
        app_commands.Choice(name='"ShowMessageOfTheDay" - Show MOTD', value="\"ShowMessageOfTheDay\""),
    ]
)
@app_commands.describe(
    server="The server to send the command to",
    command="Select a command or type a custom RCON command"
)
async def rcon_command(interaction: discord.Interaction, server: str, command: Optional[str] = None):
    """Send RCON command to server"""

    if not command:
        # Show help embed if no command specified
        embed = discord.Embed(
            title="📖 ARK RCON Commands Guide",
            description="Here are some common RCON commands you can use:",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )

        # Player Management
        embed.add_field(
            name="👥 Player Management",
            value="```\n\"ListPlayers\" - Show online players\n"
                  "\"KickPlayer <name>\" - Kick a player\n"
                  "\"BanPlayer <name>\" - Ban a player\n"
                  "\"UnbanPlayer <name>\" - Unban a player```",
            inline=False
        )

        # World Management
        embed.add_field(
            name="🌍 World Management",
            value="```\n\"SaveWorld\" - Save the current world\n"
                  "\"DestroyWildDinos\" - Remove all wild creatures\n"
                  "\"SetTimeOfDay <HH:MM>\" - Set world time```",
            inline=False
        )

        # Server Control
        embed.add_field(
            name="🔧 Server Control",
            value="```\n\"Broadcast <message>\" - Send message to all\n"
                  "\"ServerChat <message>\" - Send as SERVER```",
            inline=False
        )

        # Information
        embed.add_field(
            name="ℹ️ Information",
            value="```\n\"GetChat\" - Show recent chat\n"
                  "\"GetGameLog\" - Show game log\n"
                  "\"ShowMessageOfTheDay\" - Show MOTD```",
            inline=False
        )

        embed.set_footer(text=f"Use: /rcon {server} <command>")
        await interaction.response.send_message(embed=embed)
        return

    # Handle commands that need additional input
    command = command.strip('"')  # Remove quotes from the command value

    if command in ["KickPlayer", "BanPlayer", "UnbanPlayer"]:
        class PlayerModal(discord.ui.Modal, title=f"{command} Command"):
            player_name = discord.ui.TextInput(
                label="Player Name",
                placeholder="Enter the player's name",
                min_length=1,
                max_length=100,
            )

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer()
                try:
                    # For player commands (KickPlayer, BanPlayer, UnbanPlayer)
                    cmd = f"\"{command} {self.player_name.value}\""
                    output, color = await execute_ark_command(f"rconcmd {cmd}", server)
                    if not output:
                        output = f"Command executed: {command} on player {self.player_name.value}"
                    await send_response(interaction, f"🎮 {command}", output, color)
                except Exception as e:
                    print(f"Error in {command}: {e}")
                    await send_response(interaction, f"🎮 {command}", f"Error: {str(e)}", discord.Color.red())

        await interaction.response.send_modal(PlayerModal())
        return

    elif command == "SetTimeOfDay":
        class TimeModal(discord.ui.Modal, title="Set Time Command"):
            time = discord.ui.TextInput(
                label="Time (HH:MM)",
                placeholder="Enter time in 24-hour format (e.g., 14:30)",
                min_length=5,
                max_length=5,
            )

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer()
                try:
                    # For SetTimeOfDay command
                    cmd = f"\"SetTimeOfDay {self.time.value}\""
                    output, color = await execute_ark_command(f"rconcmd {cmd}", server)
                    if not output:
                        output = f"Time set to {self.time.value}"
                    await send_response(interaction, "🕒 Set Time", output, color)
                except Exception as e:
                    print(f"Error in SetTimeOfDay: {e}")
                    await send_response(interaction, "🕒 Set Time", f"Error: {str(e)}", discord.Color.red())

        await interaction.response.send_modal(TimeModal())
        return

    elif command in ["Broadcast", "ServerChat"]:
        class MessageModal(discord.ui.Modal, title=f"{command} Command"):
            message = discord.ui.TextInput(
                label="Message",
                placeholder="Enter your message",
                min_length=1,
                max_length=1000,
                style=discord.TextStyle.paragraph,
            )

            async def on_submit(self, interaction: discord.Interaction):
                await interaction.response.defer()
                try:
                    # For message commands (Broadcast, ServerChat)
                    cmd = f"\"{command} {self.message.value}\""
                    output, color = await execute_ark_command(f"rconcmd {cmd}", server)
                    if not output:
                        output = f"Message sent: {self.message.value}"
                    await send_response(interaction, f"📢 {command}", output, color)
                except Exception as e:
                    print(f"Error in {command}: {e}")
                    await send_response(interaction, f"📢 {command}", f"Error: {str(e)}", discord.Color.red())

        await interaction.response.send_modal(MessageModal())
        return

    # For commands that don't need additional input, execute directly
    await interaction.response.defer()
    output, color = await execute_ark_command(f"rconcmd {command}", server)
    await send_response(interaction, f"🔧 RCON Command - {server}", output, color)


@bot.event
async def on_ready():
    """Bot startup event"""
    print(f"✅ {bot.user} is now online!")
    if await ssh_client.connect():
        print("✅ Successfully connected to VPS!")
        output, color = await execute_ark_command("--version", "all")
        if "arkmanager not found" in (output or "").lower():
            print("⚠️ arkmanager needs to be installed")
        else:
            print("✅ arkmanager is installed and ready")
    else:
        print("❌ Failed to connect to VPS!")

    await bot.tree.sync()

# Start the bot
bot.run(TOKEN)