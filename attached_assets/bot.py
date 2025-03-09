import discord
import subprocess
import os
from discord.ext import commands, tasks
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

if not TOKEN:
    raise ValueError("Bot token is missing! Set DISCORD_BOT_TOKEN in your .env file.")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def get_ark_status():
    try:
        result = subprocess.run(["arkmanager", "status", "@all"], capture_output=True, text=True, check=True)
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

async def execute_ark_command(ctx, command, server_name="all"):
    cmd = ["arkmanager", command, f"@{server_name}"]
    await ctx.send(f"⏳ Executing `{command}` on **{server_name}** server...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        clean_output = "\n".join([line for line in result.stdout.split("\n") if not line.startswith("\x1b") and line.strip()])
        await ctx.send(f"```\n{clean_output or result.stderr}\n```")
    except subprocess.CalledProcessError as e:
        await ctx.send(f"❌ Command failed: {e}")

@bot.command(name="rconcmd")
async def rcon_command(ctx, server_name: str = "all", *, command: str):
    await execute_ark_command(ctx, f"rconcmd {command}", server_name)

@bot.command(name="status")
async def status(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "status", server_name)

@bot.command(name="start")
async def start_server(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "start", server_name)

@bot.command(name="stop")
async def stop_server(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "stop", server_name)

@bot.command(name="restart")
async def restart_server(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "restart", server_name)

@bot.command(name="backup")
async def backup_server(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "backup", server_name)

@bot.command(name="update")
async def update_server(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "update", server_name)

@bot.command(name="checkmodupdate")
async def check_mod_update(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "checkmodupdate", server_name)

@bot.command(name="players")
async def players(ctx, server_name: str = "all"):
    await execute_ark_command(ctx, "listplayers", server_name)

@bot.command(name="broadcast")
async def broadcast_message(ctx, *, message: str):
    cmd = ["arkmanager", "broadcast", message]
    await ctx.send(f"📢 Broadcasting message: `{message}`")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        await ctx.send(f"```\n{result.stdout or result.stderr}\n```")
    except subprocess.CalledProcessError as e:
        await ctx.send(f"❌ Broadcast failed: {e}")

@tasks.loop(minutes=2)
async def update_bot_status():
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
    update_bot_status.start()

bot.run(TOKEN)
