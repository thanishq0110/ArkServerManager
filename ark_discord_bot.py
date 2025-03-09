import discord
import os
import asyncio
import paramiko
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from typing import Optional, Dict
import re
from datetime import datetime, timedelta

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
    raise ValueError("VPS credentials are missing! Please set VPS_HOST, VPS_USERNAME, and VPS_PASSWORD in your .env file.")

# Server instances available
SERVERS = ["ragnarok", "fjordur", "main", "all"]

# Add new configuration after SERVERS
ADMIN_ROLE_NAME = "ARK Admin"
MOD_ROLE_NAME = "ARK Moderator"

# Add new permission check
def check_permissions(interaction: discord.Interaction, required_role: str) -> bool:
    """Check if user has required role"""
    return any(role.name == required_role for role in interaction.user.roles)

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
        self.max_retries = 3
        self.retry_delay = 5  # seconds

    async def connect(self):
        retries = 0
        while retries < self.max_retries:
            try:
                print(f"🔄 Attempting SSH connection to {VPS_HOST} (attempt {retries + 1}/{self.max_retries})...")
                self.ssh.connect(
                    VPS_HOST,
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

    async def execute_command(self, command):
        try:
            print(f"🔄 Executing command: {command}")
            if not self.ssh.get_transport() or not self.ssh.get_transport().is_active():
                print("⚠️ SSH connection lost, attempting reconnection...")
                if not await self.connect():
                    error_msg = "Failed to connect to VPS. Please check VPS status and credentials."
                    return error_msg, "Connection Error", discord.Color.red()

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
        if self.connected:
            self.ssh.close()
            self.connected = False
            print("📡 SSH connection closed")

ssh_client = SSHClient()

class ServerSelect(discord.ui.Select):
    def __init__(self, placeholder: str):
        options = [
            discord.SelectOption(label=server.capitalize(), value=server)
            for server in SERVERS
        ]
        super().__init__(
            placeholder=placeholder,
            min_values=1,
            max_values=1,
            options=options,
        )

class ConfirmView(discord.ui.View):
    def __init__(self, timeout: float = 180.0):
        super().__init__(timeout=timeout)
        self.value = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.send_message("Action confirmed!", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.send_message("Action cancelled!", ephemeral=True)
        self.stop()

class ServerControlView(discord.ui.View):
    def __init__(self, server: str, ssh_client):
        super().__init__(timeout=None)
        self.server = server
        self.ssh_client = ssh_client

    @discord.ui.button(label="🚀 Start", style=discord.ButtonStyle.green, custom_id="start")
    async def start_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        output, status, color = await execute_ark_command("start", self.server)
        await send_command_response(interaction, "Start Server", self.server, output, status, color)

    @discord.ui.button(label="🛑 Stop", style=discord.ButtonStyle.red, custom_id="stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to stop the server **{self.server}**?", view=view, ephemeral=True)
        await view.wait()

        if view.value:
            output, status, color = await execute_ark_command("stop", self.server)
            await send_command_response(interaction, "Stop Server", self.server, output, status, color)

    @discord.ui.button(label="🔄 Restart", style=discord.ButtonStyle.blurple, custom_id="restart")
    async def restart_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to restart the server **{self.server}**?", view=view, ephemeral=True)
        await view.wait()

        if view.value:
            output, status, color = await execute_ark_command("restart", self.server)
            await send_command_response(interaction, "Restart Server", self.server, output, status, color)

    @discord.ui.button(label="👥 Players", style=discord.ButtonStyle.gray, custom_id="players")
    async def players_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        output, status, color = await execute_ark_command("listplayer", self.server)
        await send_command_response(interaction, "Player List", self.server, output, status, color)

    @discord.ui.button(label="💾 Backup", style=discord.ButtonStyle.gray, custom_id="backup")
    async def backup_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to backup the server **{self.server}**?", view=view, ephemeral=True)
        await view.wait()

        if view.value:
            output, status, color = await execute_ark_command("backup", self.server)
            await send_command_response(interaction, "Backup Server", self.server, output, status, color)

    @discord.ui.button(label="🔄 Update", style=discord.ButtonStyle.gray, custom_id="update")
    async def update_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ConfirmView()
        await interaction.response.send_message(f"Are you sure you want to update the server **{self.server}**?", view=view, ephemeral=True)
        await view.wait()

        if view.value:
            output, status, color = await execute_ark_command("update", self.server)
            await send_command_response(interaction, "Update Server", self.server, output, status, color)

    @discord.ui.button(label="🔧 Mods", style=discord.ButtonStyle.gray, custom_id="mods")
    async def mods_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        output, status, color = await execute_ark_command("checkmodupdate", self.server)
        await send_command_response(interaction, "Mod Status", self.server, output, status, color)

    @discord.ui.button(label="📊 Quick Stats", style=discord.ButtonStyle.blurple, custom_id="stats")
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        output, status, color = await execute_ark_command("status", self.server)
        await send_command_response(interaction, "Quick Stats", self.server, output, status, color)


class PlayerManagementView(discord.ui.View):
    def __init__(self, server: str):
        super().__init__(timeout=None)
        self.server = server

    @discord.ui.button(label="👢 Kick", style=discord.ButtonStyle.primary, custom_id="kick")
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlayerActionModal(self.server, "kick", "Kick Player"))

    @discord.ui.button(label="🚫 Ban", style=discord.ButtonStyle.danger, custom_id="ban")
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(PlayerActionModal(self.server, "ban", "Ban Player"))

class PlayerActionModal(discord.ui.Modal):
    def __init__(self, server: str, action: str, title: str):
        super().__init__()
        self.title = title
        self.server = server
        self.action = action
        self.player_name = discord.ui.TextInput(
            label="Player Name",
            placeholder="Enter the player's name",
            min_length=1,
            max_length=100,
        )
        self.add_item(self.player_name)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        command = f"rconcmd {self.action}Player {self.player_name.value}"
        output, status, color = await execute_ark_command(command, self.server)
        await send_command_response(interaction, f"{self.action.title()} Player", self.server, output, status, color)

async def execute_ark_command(command: str, server_name: str) -> tuple[str, str, discord.Color]:
    """Execute ARK server command via SSH and return formatted response"""
    print(f"🎮 Executing ARK command: {command} on server: {server_name}")

    # Special handling for player list command
    if command == "listplayer":
        cmd = f"arkmanager rconcmd listplayer @{server_name}"
        print(f"📝 Player list command being executed: {cmd}")
        print(f"🎯 Server name: {server_name}")
    elif command.startswith("rconcmd"):
        # Handle other RCON commands
        cmd = f"arkmanager rconcmd {command.replace('rconcmd ', '')} @{server_name}"
    else:
        cmd = f"arkmanager {command} @{server_name}"

    print(f"🔄 Executing command: {cmd}")
    output, status, color = await ssh_client.execute_command(cmd)
    print(f"📤 Raw command output: {output}")
    print(f"📊 Command status: {status}")
    print(f"🎨 Command color: {color}")

    if "arkmanager not found" in (output or "").lower():
        print("⚠️ arkmanager not found, attempting installation...")
        install_msg = (
            "❌ Error: arkmanager not found!\n\n"
            "Installing arkmanager on your VPS...\n"
        )
        install_cmd = "curl -sL https://raw.githubusercontent.com/arkmanager/ark-server-tools/master/tools/install.sh | sudo bash -s steam"
        await ssh_client.execute_command(install_cmd)
        return install_msg, "Installing arkmanager", discord.Color.yellow()

    # Clean and format the output
    if output:
        # Remove ANSI color codes and clean up whitespace
        output = re.sub(r'\x1b\[[0-9;]*m', '', output)
        output = output.strip()

    # Format empty player list response
    if command == "listplayer":
        if not output or not output.strip():
            print("ℹ️ No players online, returning formatted message")
            output = "No players currently online"
            status = "Success"
            color = discord.Color.blue()
        else:
            print(f"👥 Found players: {output}")

    print(f"📝 Command output status: {status}")
    return output, status, color

async def send_command_response(interaction, title, server, output, status, color):
    embed = discord.Embed(
        title=f"**{title}**",
        description=f"🖥️ Server: **{server}**\n📊 Status: **{status}**",
        color=color,
        timestamp=datetime.utcnow()
    )

    # Format the output for better readability
    clean_output = output.strip()
    if clean_output:
        # Split long outputs into chunks if needed
        if len(clean_output) > 1024:
            chunks = [clean_output[i:i+1024] for i in range(0, len(clean_output), 1024)]
            for i, chunk in enumerate(chunks, 1):
                embed.add_field(
                    name=f"📝 Output (Part {i}/{len(chunks)})", 
                    value=f"```{chunk}```", 
                    inline=False
                )
        else:
            embed.add_field(name="📝 Output", value=f"```{clean_output}```", inline=False)

    # Add server info if available
    servers = await get_ark_status()
    if servers and server in servers:
        status_emoji = "🟢" if servers[server]["running"] else "🔴"
        players = servers[server]["players"]
        embed.add_field(
            name="📈 Server Stats",
            value=f"{status_emoji} Status: **{'Online' if servers[server]['running'] else 'Offline'}**\n"
                  f"👥 Players: **{players}**",
            inline=True
        )

    embed.set_footer(
        text=f"🎮 Requested by {interaction.user.name}", 
        icon_url=interaction.user.avatar.url if interaction.user.avatar else None
    )
    embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")  # ARK logo

    try:
        await interaction.followup.send(embed=embed)
    except discord.HTTPException:
        # If the embed is too large, send a simplified version
        error_embed = discord.Embed(
            title=f"**{title}** - Output Too Large",
            description=f"🖥️ Server: **{server}**\n"
                       f"📊 Status: **{status}**\n\n"
                       f"⚠️ Output was too large to display fully. Please check the server logs.",
            color=color
        )
        await interaction.followup.send(embed=error_embed)

async def get_ark_status():
    """Get status of all ARK servers via SSH"""
    try:
        print("📊 Getting ARK servers status...")
        loop = asyncio.get_event_loop()
        if loop.is_running():
            print("⚡ Creating new event loop for status check")
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

@bot.tree.command(name="broadcast", description="Broadcast a message to all players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def broadcast(interaction: discord.Interaction, server: str, message: str):
    await interaction.response.defer()
    cmd = f"arkmanager rconcmd {server} \"Broadcast {message}\""

    try:
        output, status, color = await ssh_client.execute_command(cmd)
        embed = discord.Embed(
            title="📢 Broadcast Message",
            description=f"Server: **{server}**\nMessage: *{message}*",
            color=color,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name=status, value=f"```{output}```", inline=False)
        embed.set_footer(text=f"Broadcast by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
    except Exception as e:
        embed = discord.Embed(
            title="📢 Broadcast Error",
            description=f"Failed to broadcast to server: **{server}**",
            color=discord.Color.red()
        )
        embed.add_field(name="Error", value=str(e), inline=False)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="rcon", description="Open RCON command panel")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def rcon_panel(interaction: discord.Interaction, server: str):
    class RCONModal(discord.ui.Modal, title="RCON Command"):
        def __init__(self):
            super().__init__()
            self.command = discord.ui.TextInput(
                label="Command",
                placeholder="Enter RCON command",
                min_length=1,
                max_length=100,
            )
            self.add_item(self.command)

        async def on_submit(self, interaction: discord.Interaction):
            await interaction.response.defer()
            output, status, color = await execute_ark_command(f"rconcmd {self.command.value}", server)
            await send_command_response(interaction, "RCON Command", server, output, status, color)

    await interaction.response.send_modal(RCONModal())

@bot.tree.command(name="players", description="Get a list of online players")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def players_list(interaction: discord.Interaction, server: str):
    """Get list of online players"""
    await interaction.response.defer()
    output, status, color = await execute_ark_command("listplayer", server)
    await send_command_response(interaction, "👥 Player List", server, output, status, color)


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
        status_emoji = "🟢" if servers[server]["running"] else "🔴"
        players = servers[server]["players"]
        connect_link = servers[server]["connect"]

        embed.add_field(
            name="📊 Server Status",
            value=f"{status_emoji} Status: **{'Online' if servers[server]['running'] else 'Offline'}**\n"
                  f"👥 Players: **{players}**\n"
                  f"🔗 Connect: ```{connect_link}```",
            inline=False
        )

    # Add quick action buttons
    class QuickActionsView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=None)

        @discord.ui.button(label="🔄 Refresh", style=discord.ButtonStyle.gray)
        async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
            await server_info(interaction, server)

        @discord.ui.button(label="👥 Players", style=discord.ButtonStyle.primary)
        async def players(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            output, status, color = await execute_ark_command("listplayer", server)
            await send_command_response(interaction, "Player List", server, output, status, color)

    view = QuickActionsView()
    await interaction.followup.send(embed=embed, view=view)


@bot.tree.command(name="serverstatus", description="Get the status of all servers")
async def get_server_status(interaction: discord.Interaction):
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


@tasks.loop(minutes=2)
async def update_bot_status():
    """Update bot status with server information"""
    servers = await get_ark_status()
    if not servers:
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="⚠️ Server Status Unavailable"
            )
        )
        return

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

@bot.event
async def on_ready():
    print(f"✅ {bot.user} is now online!")
    if await ssh_client.connect():
        print("✅ Successfully connected to VPS!")
        # Test VPS connection and arkmanager installation
        output, status, color = await execute_ark_command("version", "all")
        if "arkmanager not found" in (output or "").lower():
            print("⚠️ arkmanager needs to be installed")
        else:
            print("✅ arkmanager is installed and ready")
    else:
        print("❌ Failed to connect to VPS! Please check your credentials.")
    await bot.tree.sync()
    update_bot_status.start()

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
            await send_command_response(interaction, "Update Mods", self.server, output, output, status, color)

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
        embed.set_thumbnail(url="https://i.imgur.com/1Fj9ZlA.png")  # Fixed typo in embed.set_thumbnail

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

bot.run(TOKEN)