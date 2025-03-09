import discord
import subprocess
import os
import asyncio
import paramiko
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
VPS_HOST = os.getenv("VPS_HOST")
VPS_USERNAME = os.getenv("VPS_USERNAME")
VPS_PASSWORD = os.getenv("VPS_PASSWORD")

if not TOKEN:
    raise ValueError("Bot token is missing! Set DISCORD_BOT_TOKEN in your .env file.")
if not all([VPS_HOST, VPS_USERNAME, VPS_PASSWORD]):
    raise ValueError("VPS credentials are missing! Please set VPS_HOST, VPS_USERNAME, and VPS_PASSWORD in your .env file.")

# Server instances available
SERVERS = ["ragnarok", "fjordur", "main", "all"]

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

class SSHClient:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    async def connect(self):
        try:
            self.ssh.connect(VPS_HOST, username=VPS_USERNAME, password=VPS_PASSWORD)
            return True
        except Exception as e:
            print(f"SSH connection error: {e}")
            return False

    async def execute_command(self, command):
        try:
            if not self.ssh.get_transport() or not self.ssh.get_transport().is_active():
                if not await self.connect():
                    return "Failed to connect to VPS", "Error", discord.Color.red()

            stdin, stdout, stderr = self.ssh.exec_command(command)
            output = stdout.read().decode()
            error = stderr.read().decode()

            if error and not output:
                return error, "Error", discord.Color.red()
            return output or "Command executed successfully", "Success", discord.Color.green()
        except Exception as e:
            return str(e), "Error", discord.Color.red()

    def close(self):
        self.ssh.close()

ssh_client = SSHClient()

async def execute_ark_command(command: str, server_name: str) -> tuple[str, str, discord.Color]:
    """Execute ARK server command via SSH and return formatted response"""
    cmd = f"arkmanager {command} @{server_name}"
    output, status, color = await ssh_client.execute_command(cmd)

    if "arkmanager not found" in output.lower():
        install_msg = (
            "❌ Error: arkmanager not found!\n\n"
            "Installing arkmanager on your VPS...\n"
        )
        install_cmd = "curl -sL https://raw.githubusercontent.com/arkmanager/ark-server-tools/master/tools/install.sh | sudo bash -s steam"
        await ssh_client.execute_command(install_cmd)
        return install_msg, "Installing arkmanager", discord.Color.yellow()

    return output, status, color

def get_ark_status():
    """Get status of all ARK servers via SSH"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new event loop for the blocking call
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            output, _, _ = new_loop.run_until_complete(ssh_client.execute_command("arkmanager status @all"))
            new_loop.close()
        else:
            output, _, _ = loop.run_until_complete(ssh_client.execute_command("arkmanager status @all"))

        lines = output.split("\n")
        servers = {}
        current_server = None

        for line in lines:
            line = line.strip()
            if "Running command 'status' for instance" in line:
                current_server = line.split("'")[3]
                servers[current_server] = {"running": False, "players": 0, "connect": "None"}
            elif current_server:
                if "Server running:" in line:
                    servers[current_server]["running"] = "Yes" in line
                elif "Steam Players:" in line:
                    try:
                        players = int(line.split(":")[-1].strip().split("/")[0])
                        servers[current_server]["players"] = players
                    except (ValueError, IndexError):
                        servers[current_server]["players"] = 0
                elif "Steam connect link:" in line:
                    servers[current_server]["connect"] = line.split(": ", 1)[-1].strip()
        return servers
    except Exception as e:
        print(f"Error getting ark status: {e}")
        return None

@bot.tree.command(name="start", description="Start the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def start_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("start", server)
    
    embed = discord.Embed(
        title="🚀 Server Start Command",
        description=f"Starting server: **{server}**",
        color=color
    )
    embed.add_field(name=status, value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="stop", description="Stop the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def stop_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("stop", server)
    
    embed = discord.Embed(
        title="🛑 Server Stop Command",
        description=f"Stopping server: **{server}**",
        color=color
    )
    embed.add_field(name=status, value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="restart", description="Restart the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def restart_server(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("restart", server)
    
    embed = discord.Embed(
        title="🔄 Server Restart Command",
        description=f"Restarting server: **{server}**",
        color=color
    )
    embed.add_field(name=status, value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="status", description="Get server status")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def status(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("status", server)
    
    embed = discord.Embed(
        title="📊 Server Status",
        description=f"Status for server: **{server}**",
        color=color
    )
    embed.add_field(name="Details", value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="players", description="List online players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def players(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("listplayers", server)
    
    embed = discord.Embed(
        title="👥 Online Players",
        description=f"Players on server: **{server}**",
        color=color
    )
    embed.add_field(name="Player List", value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="broadcast", description="Broadcast a message to all players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def broadcast(interaction: discord.Interaction, server: str, message: str):
    await interaction.response.defer()
    cmd = f"arkmanager rconcmd @{server} \"Broadcast {message}\""
    
    try:
        output, status, color = await ssh_client.execute_command(cmd)
        embed = discord.Embed(
            title="📢 Broadcast Message",
            description=f"Server: **{server}**\nMessage: *{message}*",
            color=color
        )
        embed.add_field(name=status, value=f"```{output}```", inline=False)
    except Exception as e:
        embed = discord.Embed(
            title="📢 Broadcast Error",
            description=f"Failed to broadcast to server: **{server}**",
            color=discord.Color.red()
        )
        embed.add_field(name="Error", value=str(e), inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="backup", description="Create a server backup")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def backup(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("backup", server)
    
    embed = discord.Embed(
        title="💾 Server Backup",
        description=f"Creating backup for server: **{server}**",
        color=color
    )
    embed.add_field(name=status, value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="update", description="Update server and mods")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def update(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("update", server)
    
    embed = discord.Embed(
        title="🔄 Server Update",
        description=f"Updating server: **{server}**",
        color=color
    )
    embed.add_field(name=status, value=f"```{output}```", inline=False)
    
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="rcon", description="Execute RCON command")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def rcon(interaction: discord.Interaction, server: str, command: str):
    await interaction.response.defer()
    cmd = f"arkmanager rconcmd @{server} \"{command}\""
    
    try:
        output, status, color = await ssh_client.execute_command(cmd)
        embed = discord.Embed(
            title="🎮 RCON Command",
            description=f"Server: **{server}**\nCommand: `{command}`",
            color=color
        )
        embed.add_field(name=status, value=f"```{output}```", inline=False)
    except Exception as e:
        embed = discord.Embed(
            title="🎮 RCON Error",
            description=f"Failed to execute command on server: **{server}**",
            color=discord.Color.red()
        )
        embed.add_field(name="Error", value=str(e), inline=False)
    
    await interaction.followup.send(embed=embed)

@tasks.loop(minutes=2)
async def update_bot_status():
    """Update bot status with server information"""
    servers = get_ark_status()
    if not servers:
        await bot.change_presence(activity=discord.Game(name="⚠️ Error fetching status"))
        return
    
    total_players = sum(info["players"] for info in servers.values() if info["running"])
    online_servers = sum(1 for info in servers.values() if info["running"])
    status_message = f"🎮 {total_players} players on {online_servers} servers" if online_servers > 0 else "❌ No servers online"
    await bot.change_presence(activity=discord.Game(name=status_message))

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is now online!")
    if await ssh_client.connect():
        print("✅ Successfully connected to VPS!")
    else:
        print("❌ Failed to connect to VPS! Please check your credentials.")
    await bot.tree.sync()
    update_bot_status.start()

bot.run(TOKEN)