import discord
import os
import asyncio
import paramiko
import re
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime
from typing import Optional, Dict, Tuple

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

# Server instances available
SERVERS = ["ragnarok", "fjordur", "main", "all"]

# Admin roles configuration
ADMIN_ROLE_NAME = "ARK Admin"
MOD_ROLE_NAME = "ARK Moderator"

# Setup bot with intents
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

def check_permissions(interaction: discord.Interaction, required_role: str) -> bool:
    """Check if user has required role"""
    return any(role.name == required_role for role in interaction.user.roles)

class SSHClient:
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print("📡 SSH client initialized")
        self.connected = False
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    async def connect(self) -> bool:
        """Establish SSH connection with retry mechanism"""
        retries = 0
        while retries < self.max_retries:
            try:
                print(f"🔄 Attempting SSH connection to {VPS_HOST} (attempt {retries + 1}/{self.max_retries})...")
                self.ssh.connect(
                    hostname=VPS_HOST,
                    username=VPS_USERNAME,
                    password=VPS_PASSWORD,
                    timeout=30
                )
                self.connected = True
                print("✅ SSH connection successful")
                return True
            except paramiko.AuthenticationException as e:
                print(f"❌ Authentication failed: {e}")
                return False
            except paramiko.SSHException as e:
                print(f"❌ SSH error: {e}")
            except Exception as e:
                print(f"❌ Connection error: {e}")

            retries += 1
            if retries < self.max_retries:
                print(f"⏳ Waiting {self.retry_delay} seconds before retry...")
                await asyncio.sleep(self.retry_delay)

        print("❌ Maximum connection retries reached")
        return False

    async def execute_command(self, command: str) -> Tuple[str, str, discord.Color]:
        """Execute command via SSH and return formatted response"""
        try:
            print(f"🔄 Executing command: {command}")
            if not self.ssh.get_transport() or not self.ssh.get_transport().is_active():
                print("⚠️ SSH connection lost, attempting reconnection...")
                if not await self.connect():
                    return "Failed to connect to VPS", "Connection Error", discord.Color.red()

            print("📤 Sending command to VPS...")
            stdin, stdout, stderr = self.ssh.exec_command(command, timeout=60)
            output = stdout.read().decode()
            error = stderr.read().decode()

            print(f"📥 Command output: {output}")
            if error:
                print(f"⚠️ Command stderr: {error}")

            if error and not output:
                print(f"❌ Command error: {error}")
                return error, "Error", discord.Color.red()

            # Clean ANSI color codes and whitespace
            output = re.sub(r'\x1b\[[0-9;]*m', '', output)
            output = output.strip()

            print(f"✅ Command executed successfully")
            return output or "Command executed successfully", "Success", discord.Color.green()

        except paramiko.SSHException as e:
            error_msg = f"SSH error: {e}"
            print(f"❌ {error_msg}")
            return error_msg, "SSH Error", discord.Color.red()
        except Exception as e:
            error_msg = f"Error executing command: {e}"
            print(f"❌ {error_msg}")
            return error_msg, "Error", discord.Color.red()

    def close(self):
        """Close SSH connection"""
        if self.connected:
            self.ssh.close()
            self.connected = False
            print("📡 SSH connection closed")

ssh_client = SSHClient()

# Command execution and format handling
async def execute_ark_command(command: str, server_name: str) -> Tuple[str, str, discord.Color]:
    """Execute ARK server command via SSH and return formatted response"""
    print(f"🎮 Executing ARK command: {command} on server: {server_name}")

    # Special handling for player list command
    if command == "listplayers":
        cmd = f"arkmanager rconcmd listplayers @{server_name}"
        print(f"📝 Player list command: {cmd}")
    elif command.startswith("rconcmd"):
        # Handle other RCON commands
        rcon_cmd = command.replace('rconcmd ', '')
        cmd = f"arkmanager rconcmd {rcon_cmd} @{server_name}"
    else:
        # Regular arkmanager commands
        cmd = f"arkmanager {command} @{server_name}"

    print(f"🔄 Executing command: {cmd}")
    output, status, color = await ssh_client.execute_command(cmd)
    print(f"📤 Raw command output: {output}")

    if "arkmanager not found" in (output or "").lower():
        print("⚠️ arkmanager not found, attempting installation...")
        install_msg = (
            "❌ Error: arkmanager not found!\n\n"
            "Installing arkmanager on your VPS...\n"
        )
        install_cmd = "curl -sL https://raw.githubusercontent.com/arkmanager/ark-server-tools/master/tools/install.sh | sudo bash -s steam"
        await ssh_client.execute_command(install_cmd)
        return install_msg, "Installing arkmanager", discord.Color.yellow()

    # Format empty player list response
    if command == "listplayers":
        if not output or not output.strip():
            output = "No players currently online"
            status = "Success"
            color = discord.Color.blue()
        else:
            # Clean up player list output
            lines = [line.strip() for line in output.split('\n') if line.strip()]
            output = '\n'.join(lines)

    # Clean ANSI color codes and whitespace
    if output:
        output = re.sub(r'\x1b\[[0-9;]*m', '', output)
        output = output.strip()

    print(f"📝 Command output status: {status}")
    return output, status, color

async def send_command_response(interaction: discord.Interaction, title: str, server: str, output: str, status: str, color: discord.Color):
    """Send formatted command response as Discord embed"""
    embed = discord.Embed(
        title=f"**{title}**",
        description=f"🖥️ Server: **{server}**\n📊 Status: **{status}**",
        color=color,
        timestamp=datetime.utcnow()
    )

    # Format the output
    if output:
        output = output.strip()
        if len(output) > 1024:
            chunks = [output[i:i+1024] for i in range(0, len(output), 1024)]
            for i, chunk in enumerate(chunks, 1):
                embed.add_field(
                    name=f"📝 Output (Part {i}/{len(chunks)})",
                    value=f"```{chunk}```",
                    inline=False
                )
        else:
            embed.add_field(name="📝 Output", value=f"```{output}```", inline=False)

    embed.set_footer(text=f"🎮 Requested by {interaction.user.name}")
    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")

    try:
        await interaction.followup.send(embed=embed)
    except discord.HTTPException:
        error_embed = discord.Embed(
            title=f"**{title}** - Output Too Large",
            description=f"🖥️ Server: **{server}**\n"
                       f"📊 Status: **{status}**\n\n"
                       f"⚠️ Output was too large to display fully. Please check the server logs.",
            color=color
        )
        await interaction.followup.send(embed=error_embed)

# Command definitions
@bot.tree.command(name="players", description="Get a list of online players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def players_list(interaction: discord.Interaction, server: str):
    """Get list of online players"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("listplayers", server)
    await send_command_response(interaction, "👥 Player List", server, output, status, color)

@bot.tree.command(name="start", description="Start the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def start_server(interaction: discord.Interaction, server: str):
    """Start the ARK server"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("start", server)
    await send_command_response(interaction, "🚀 Start Server", server, output, status, color)

@bot.tree.command(name="stop", description="Stop the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def stop_server(interaction: discord.Interaction, server: str):
    """Stop the ARK server"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("stop", server)
    await send_command_response(interaction, "🛑 Stop Server", server, output, status, color)

@bot.tree.command(name="restart", description="Restart the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def restart_server(interaction: discord.Interaction, server: str):
    """Restart the ARK server"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("restart", server)
    await send_command_response(interaction, "🔄 Restart Server", server, output, status, color)

@bot.tree.command(name="status", description="Get server status")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def server_status_single(interaction: discord.Interaction, server: str):
    """Get server status"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("status", server)
    await send_command_response(interaction, "📊 Server Status", server, output, status, color)

@bot.tree.command(name="backup", description="Create a server backup")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def backup_server(interaction: discord.Interaction, server: str):
    """Create a server backup"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("backup", server)
    await send_command_response(interaction, "💾 Server Backup", server, output, status, color)

@bot.tree.command(name="update", description="Update the ARK server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def update_server(interaction: discord.Interaction, server: str):
    """Update the ARK server"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("update", server)
    await send_command_response(interaction, "🔄 Server Update", server, output, status, color)

@bot.tree.command(name="broadcast", description="Broadcast a message to all players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def broadcast_message(interaction: discord.Interaction, server: str, message: str):
    """Broadcast a message to all players"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command(f"rconcmd \"Broadcast {message}\"", server)
    await send_command_response(interaction, "📢 Broadcast Message", server, output, status, color)

@bot.tree.command(name="rcon", description="Send RCON command to server")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def rcon_command(interaction: discord.Interaction, server: str, command: str):
    """Send RCON command to server"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command(f"rconcmd {command}", server)
    await send_command_response(interaction, "🔧 RCON Command", server, output, status, color)

@bot.tree.command(name="serverstatus", description="Get the status of all servers")
async def get_server_status(interaction: discord.Interaction):
    """Get status of all ARK servers"""
    await interaction.response.defer()
    servers = await get_ark_status()

    if not servers:
        embed = discord.Embed(
            title="❌ **Error**",
            description="Failed to retrieve server status. Please check server logs.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        await interaction.followup.send(embed=embed)
        return

    total_players = sum(info["players"] for info in servers.values() if info["running"])
    online_servers = sum(1 for info in servers.values() if info["running"])

    embed = discord.Embed(
        title="🎮 **ARK Server Status**",
        description=f"📊 Overview\n"
                   f"💻 Servers Online: **{online_servers}/{len(servers)}**\n"
                   f"👥 Total Players: **{total_players}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    for server_name, server_info in servers.items():
        status_emoji = "🟢" if server_info["running"] else "🔴"
        players = server_info["players"]
        connect_info = f"```{server_info['connect']}```" if server_info["running"] else "*Offline*"

        embed.add_field(
            name=f"📡 {server_name.capitalize()}",
            value=f"{status_emoji} Status: **{'Online' if server_info['running'] else 'Offline'}**\n"
                  f"👥 Players: **{players}**\n"
                  f"🔗 Connect: {connect_info}",
            inline=False
        )

    embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")
    await interaction.followup.send(embed=embed)

async def get_ark_status():
    """Get status of all ARK servers via SSH"""
    try:
        print("📊 Getting ARK servers status...")
        output, _, _ = await ssh_client.execute_command("arkmanager status @all")

        lines = output.split("\n")
        servers = {}
        current_server = None

        for line in lines:
            line = line.strip()
            if "Running command 'status' for instance" in line:
                current_server = line.split("'")[3]
                print(f"🖥️ Processing status for server: {current_server}")
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

        print(f"✅ Successfully processed status for {len(servers)} servers")
        return servers
    except Exception as e:
        print(f"❌ Error getting ark status: {e}")
        return None

@bot.event
async def on_ready():
    """Bot startup event"""
    print(f"✅ {bot.user} is now online!")
    if await ssh_client.connect():
        print("✅ Successfully connected to VPS!")
        # Test arkmanager installation
        output, status, color = await execute_ark_command("--version", "all")
        if "arkmanager not found" in (output or "").lower():
            print("⚠️ arkmanager needs to be installed")
        else:
            print("✅ arkmanager is installed and ready")
    else:
        print("❌ Failed to connect to VPS! Please check your credentials.")

    await bot.tree.sync()
    update_bot_status.start()

@tasks.loop(minutes=2)
async def update_bot_status():
    """Update bot status with server information"""
    print("🔄 Updating bot status...")
    servers = await get_ark_status()

    if not servers:
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="⚠️ Server Status Unavailable"
            )
        )
        return

    # Parse player count from status output
    total_players = sum(info["players"] for info in servers.values() if info["running"])
    online_servers = sum(1 for info in servers.values() if info["running"])

    if online_servers > 0:
        status = discord.Status.online
        activity_type = discord.ActivityType.playing
        status_message = f"🎮 {total_players} players on {online_servers} servers"
    else:
        status = discord.Status.idle
        activity_type = discord.ActivityType.watching
        status_message = "❌ No servers online"

    await bot.change_presence(
        status=status,
        activity=discord.Activity(
            type=activity_type,
            name=status_message
        )
    )
    print(f"✅ Bot status updated: {status_message}")

class ConfirmView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.value = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value= False
        self.stop()
        await interaction.response.defer()

class ServerControlView(discord.ui.View):
    def __init__(self, server: str, ssh_client: SSHClient):
        super().__init__(timeout=None)
        self.server = server
        self.ssh_client = ssh_client

    @discord.ui.button(label="Start Server", style=discord.ButtonStyle.success)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, ADMIN_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Admin role to use this command!", ephemeral=True)
            return
        await interaction.response.defer()
        output, status, color = await execute_ark_command("start", self.server)
        await send_command_response(interaction, "🚀 Server Started", self.server, output, status, color)

    @discord.ui.button(label="Stop Server", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, ADMIN_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Admin role to use this command!", ephemeral=True)
            return
        await interaction.response.defer()
        output, status, color = await execute_ark_command("stop", self.server)
        await send_command_response(interaction, "🛑 Server Stopped", self.server, output, status, color)

    @discord.ui.button(label="Restart Server", style=discord.ButtonStyle.blurple)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, ADMIN_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Admin role to use this command!", ephemeral=True)
            return
        await interaction.response.defer()
        output, status, color = await execute_ark_command("restart", self.server)
        await send_command_response(interaction, "🔄 Server Restarted", self.server, output, status, color)

    @discord.ui.button(label="Backup Server", style=discord.ButtonStyle.gray)
    async def backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, ADMIN_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Admin role to use this command!", ephemeral=True)
            return
        await interaction.response.defer()
        output, status, color = await execute_ark_command("backup", self.server)
        await send_command_response(interaction, "💾 Server Backed Up", self.server, output, status, color)

    @discord.ui.button(label="Update Server", style=discord.ButtonStyle.green)
    async def update(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, ADMIN_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Admin role to use this command!", ephemeral=True)
            return
        await interaction.response.defer()
        output, status, color = await execute_ark_command("update", self.server)
        await send_command_response(interaction, "🔄 Server Updated", self.server, output, status, color)

    @discord.ui.button(label="Mod Management", style=discord.ButtonStyle.primary)
    async def mod_management(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, MOD_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Moderator role to use this command!", ephemeral=True)
            return
        view = ModManagementView(self.server)
        await interaction.response.send_message("Mod Management Panel:", view=view)

    @discord.ui.button(label="Server Stats", style=discord.ButtonStyle.secondary)
    async def server_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ServerStatsView(self.server)
        await interaction.response.send_message("Server Stats Panel:", view=view)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return check_permissions(interaction, ADMIN_ROLE_NAME) or check_permissions(interaction, MOD_ROLE_NAME)

class ModManagementView(discord.ui.View):
    def __init__(self, server: str):
        super().__init__(timeout=None)
        self.server = server

    @discord.ui.button(label="📥 Check Updates", style=discord.ButtonStyle.primary)
    async def check_updates(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, MOD_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Moderator role to use this command!", ephemeral=True)
            return

        await interaction.response.defer()
        output, status, color = await execute_ark_command("checkmodupdate", self.server)

        # Parse installed mods
        mod_ids = []
        for line in output.split('\n'):
            if 'Mod ID:' in line:
                mod_id = line.split(':')[1].strip()
                mod_ids.append(mod_id)

        embed = discord.Embed(
            title="📦 **Mod Status**",
            description=f"Mod information for server: **{self.server}**",
            color=color,
            timestamp=datetime.utcnow()
        )

        if mod_ids:
            embed.add_field(
                name="📥 Installed Mods",
                value=f"```{', '.join(mod_ids)}```",
                inline=False
            )
        else:
            embed.add_field(
                name="📦 Installed Mods",
                value="No mods installed",
                inline=False
            )

        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")
        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="🔄 Update Mods", style=discord.ButtonStyle.success)
    async def update_mods(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not check_permissions(interaction, ADMIN_ROLE_NAME):
            await interaction.response.send_message("❌ You need the ARK Admin role to use this command!", ephemeral=True)
            return

        view = ConfirmView()
        await interaction.response.send_message(
            f"⚠️ Are you sure you want to update mods for **{self.server}**?\nThis will restart the server if updates are found.",
            view=view,
            ephemeral=True
        )
        await view.wait()

        if view.value:
            await interaction.response.defer()
            output, status, color = await execute_ark_command("update --update-mods", self.server)
            await send_command_response(interaction, "Update Mods", self.server, output, status, color)

class ServerStatsView(discord.ui.View):
    def __init__(self, server: str):
        super().__init__(timeout=None)
        self.server = server

    @discord.ui.button(label="📊 Performance", style=discord.ButtonStyle.primary)
    async def performance(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Get server performance stats
        cmd = f"arkmanager rconcmd stat unit @{self.server}"
        output, status, color = await ssh_client.execute_command(cmd)

        # Parse and format stats
        fps_match = re.search(r"Frame:\s*([\d.]+)ms", output)
        fps = round(1000 / float(fps_match.group(1))) if fps_match else "N/A"

        embed = discord.Embed(
            title="🖥️ **Server Performance**",
            description=f"Performance stats for **{self.server}**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🎯 FPS", value=f"**{fps}** FPS", inline=True)
        embed.set_footer(text=f"Requestedby {interaction.user.name}")
        embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="📈 Resources", style=discord.ButtonStyle.primary)
    async def resources(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cmd = "top -bn1 | grep \"Cpu\\|Mem\""
        output, status, color = await ssh_client.execute_command(cmd)

        # Parse CPU and memory usage
        lines = output.split('\n')
        cpu_usage = "N/A"
        mem_usage = "N/A"

        for line in lines:
            if 'Cpu' in line:
                cpu_match = re.search(r"(\d+\.\d+)\s*id", line)
                if cpu_match:
                    cpu_usage = f"{100 - float(cpu_match.group(1))}%"
            elif 'Mem' in line:
                mem_match = re.search(r"(\d+)\s*free,\s*(\d+)\s*used", line)
                if mem_match:
                    total = int(mem_match.group(1)) + int(mem_match.group(2))
                    used_percent = (int(mem_match.group(2)) / total) * 100
                    mem_usage = f"{used_percent:.1f}%"

        embed = discord.Embed(
            title="💻 **Server Resources**",
            description=f"Resource usage for **{self.server}**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🔄 CPU Usage", value=f"**{cpu_usage}**", inline=True)
        embed.add_field(name="💾 Memory Usage", value=f"**{mem_usage}**", inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.name}")
        embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")

        await interaction.followup.send(embed=embed)

    @discord.ui.button(label="👥 Players", style=discord.ButtonStyle.primary)
    async def players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        output, status, color = await execute_ark_command("listplayers", self.server)
        await send_command_response(interaction, "Player List", self.server, output, status, color)


@bot.tree.command(name="control", description="Open server control panel")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def control_panel(interaction: discord.Interaction, server: str):
    await interaction.response.defer()

    embed = discord.Embed(
        title="🎮 **ARK Server Control Panel**",
        description=f"Control panel for server: **{server}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    servers = await get_ark_status()
    if servers and server in servers:
        status_emoji = "🟢" if servers[server]["running"] else "🔴"
        players = servers[server]["players"]
        embed.add_field(name="📊 Status", value=f"{status_emoji} **{'Online' if servers[server]['running'] else 'Offline'}**", inline=True)
        embed.add_field(name="👥 Players", value=f"**{players}**", inline=True)
        embed.add_field(name="🔗 Connect", value=f"```{servers[server]['connect']}```", inline=False)

    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")
    embed.set_footer(text=f"Control panel opened by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

    view = ServerControlView(server, ssh_client)
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="info", description="Get detailed server information")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def server_info(interaction: discord.Interaction, server: str):
    await interaction.response.defer()
    output, status, color = await execute_ark_command("status", server)

    embed = discord.Embed(
        title=f"🖥️ **ARK Server Information**",
        description=f"Detailed information for server: **{server}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )

    servers = await get_ark_status()
    if servers and server in servers:
        status_emoji = "🟢" if servers[server]["running"] else "{connect_info}