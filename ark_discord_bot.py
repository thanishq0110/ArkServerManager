import discord
import subprocess
import os
import asyncio
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise ValueError("Bot token is missing! Set DISCORD_BOT_TOKEN in your .env file.")

# Server instances available
SERVERS = ["ragnarok", "fjordur", "main", "all"]

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

def get_ark_status():
    """Get status of all ARK servers"""
    try:
        result = subprocess.run(["arkmanager", "status", "@all"], 
                              capture_output=True, text=True, check=True)
        output = result.stdout.split("\n")
        
        servers = {}
        current_server = None
        
        for line in output:
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
    except subprocess.CalledProcessError as e:
        print(f"Error executing arkmanager: {e}")
        return None

async def execute_ark_command(command: str, server_name: str) -> tuple[str, str, discord.Color]:
    """Execute ARK server command and return formatted response"""
    cmd = ["arkmanager", command, f"@{server_name}"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        output = result.stdout or result.stderr
        clean_output = "\n".join([line for line in output.split("\n") 
                                if not line.startswith("\x1b") and line.strip()])
        return clean_output, "Success", discord.Color.green()
    except subprocess.CalledProcessError as e:
        return str(e), "Error", discord.Color.red()

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
    cmd = ["arkmanager", "rconcmd", f"@{server}", f"Broadcast {message}"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        embed = discord.Embed(
            title="📢 Broadcast Message",
            description=f"Server: **{server}**\nMessage: *{message}*",
            color=discord.Color.green()
        )
        embed.add_field(name="Status", value="Message broadcast successfully", inline=False)
    except subprocess.CalledProcessError as e:
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
    cmd = ["arkmanager", "rconcmd", f"@{server}", command]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        embed = discord.Embed(
            title="🎮 RCON Command",
            description=f"Server: **{server}**\nCommand: `{command}`",
            color=discord.Color.green()
        )
        embed.add_field(name="Output", value=f"```{result.stdout or 'Command executed successfully'}```", inline=False)
    except subprocess.CalledProcessError as e:
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
    await bot.tree.sync()
    update_bot_status.start()

bot.run(TOKEN)
