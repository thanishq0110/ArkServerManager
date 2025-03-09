import discord
import os
import asyncio
import subprocess
from discord.ext import commands
from discord import app_commands

TOKEN = "YOUR_DISCORD_BOT_TOKEN"
SERVERS = ["ragnarok", "fjordur", "main", "all"]

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

def execute_command(command):
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        return result.stdout or result.stderr
    except Exception as e:
        return str(e)

# Server Management Commands
@bot.tree.command(name="start", description="Start the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def start_server(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager start @{server}")
    embed = discord.Embed(title="🚀 Start Server", description=f"Starting **{server}**...", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="stop", description="Stop the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def stop_server(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager stop @{server}")
    embed = discord.Embed(title="🛑 Stop Server", description=f"Stopping **{server}**...", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="restart", description="Restart the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def restart_server(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager restart @{server}")
    embed = discord.Embed(title="🔄 Restart Server", description=f"Restarting **{server}**...", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="status", description="Get detailed status of an ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def server_status(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager status @{server}")
    embed = discord.Embed(title=f"🖥️ ARK Server Status: {server}", color=discord.Color.blue())
    embed.add_field(name="Server Info", value=f"```{output}```", inline=False)
    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")
    embed.set_footer(text="Use /rcon for more commands")
    await interaction.response.send_message(embed=embed)

# Player Management Commands
@bot.tree.command(name="ban", description="Ban a player from the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def ban_player(interaction: discord.Interaction, server: str, player_name: str):
    output = execute_command(f"arkmanager rconcmd @{server} BanPlayer {player_name}")
    embed = discord.Embed(title="🚫 Ban Player", description=f"Banned **{player_name}** from **{server}**", color=discord.Color.red())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kick", description="Kick a player from the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def kick_player(interaction: discord.Interaction, server: str, player_name: str):
    output = execute_command(f"arkmanager rconcmd @{server} KickPlayer {player_name}")
    embed = discord.Embed(title="👢 Kick Player", description=f"Kicked **{player_name}** from **{server}**", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="broadcast", description="Broadcast a message to the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def broadcast_message(interaction: discord.Interaction, server: str, message: str):
    output = execute_command(f"arkmanager rconcmd @{server} Broadcast {message}")
    embed = discord.Embed(title="📢 Broadcast Message", description=f"**Message:** {message}\n**Server:** {server}", color=discord.Color.gold())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="players", description="Get a list of online players on the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def players_list(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager rconcmd @{server} ListPlayers")
    embed = discord.Embed(title=f"🎮 Online Players - {server}", description=f"```{output}```", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

# Backup & Maintenance Commands
@bot.tree.command(name="backup", description="Create a backup of the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def backup_server(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager backup @{server}")
    embed = discord.Embed(title="💾 Server Backup", description=f"Backup created for **{server}**", color=discord.Color.green())
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="update", description="Update the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def update_server(interaction: discord.Interaction, server: str):
    output = execute_command(f"arkmanager update @{server}")
    embed = discord.Embed(title="🔧 Server Update", description=f"Updating **{server}**...", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

# RCON Command Execution
@bot.tree.command(name="rcon", description="Send RCON command to ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def rcon_command(interaction: discord.Interaction, server: str, command: str):
    output = execute_command(f"arkmanager rconcmd @{server} {command}")
    embed = discord.Embed(title=f"🕹️ RCON Command - {server}", description=f"```{output}```", color=discord.Color.orange())
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ {bot.user} is now online and slash commands are ready!")

bot.run(TOKEN)
