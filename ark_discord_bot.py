import discord
import os
import asyncio
import paramiko
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime

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
        output, status, color = await execute_ark_command("listplayers", self.server)
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
    cmd = f"arkmanager {command} @{server_name}"
    output, status, color = await ssh_client.execute_command(cmd)

    if "arkmanager not found" in output.lower():
        print("⚠️ arkmanager not found, attempting installation...")
        install_msg = (
            "❌ Error: arkmanager not found!\n\n"
            "Installing arkmanager on your VPS...\n"
        )
        install_cmd = "curl -sL https://raw.githubusercontent.com/arkmanager/ark-server-tools/master/tools/install.sh | sudo bash -s steam"
        await ssh_client.execute_command(install_cmd)
        return install_msg, "Installing arkmanager", discord.Color.yellow()

    print(f"📝 Command output status: {status}")
    return output, status, color

async def send_command_response(interaction, title, server, output, status, color):
    embed = discord.Embed(
        title=f"{title}",
        description=f"Server: **{server}**\nStatus: **{status}**",
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
                    name=f"Output (Part {i}/{len(chunks)})", 
                    value=f"```{chunk}```", 
                    inline=False
                )
        else:
            embed.add_field(name="Output", value=f"```{clean_output}```", inline=False)

    embed.set_footer(
        text=f"Requested by {interaction.user.name}", 
        icon_url=interaction.user.avatar.url if interaction.user.avatar else None
    )

    try:
        await interaction.followup.send(embed=embed)
    except discord.HTTPException:
        # If the embed is too large, send a simplified version
        error_embed = discord.Embed(
            title=f"{title} - Output Too Large",
            description=f"Server: **{server}**\nStatus: **{status}**\n\nOutput was too large to display fully. Please check the server logs.",
            color=color
        )
        await interaction.followup.send(embed=error_embed)


def get_ark_status():
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
        title="🎮 ARK Server Control Panel",
        description=f"Control panel for server: **{server}**",
        color=discord.Color.blue()
    )

    servers = get_ark_status()
    if servers and server in servers:
        status = "🟢 Online" if servers[server]["running"] else "🔴 Offline"
        players = servers[server]["players"]
        embed.add_field(name="Status", value=status, inline=True)
        embed.add_field(name="Players", value=str(players), inline=True)
        embed.add_field(name="Connect", value=f"```{servers[server]['connect']}```", inline=False)

    view = ServerControlView(server, ssh_client)
    await interaction.followup.send(embed=embed, view=view)

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

@bot.tree.command(name="players", description="Open player management panel")
@app_commands.choices(server=[app_commands.Choice(name=s, value=s) for s in SERVERS])
async def player_management(interaction: discord.Interaction, server: str):
    await interaction.response.defer()

    output, status, color = await execute_ark_command("listplayers", server)
    embed = discord.Embed(
        title="👥 Player Management",
        description=f"Server: **{server}**",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow()
    )
    embed.add_field(name="Online Players", value=f"```{output}```", inline=False)
    embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

    view = PlayerManagementView(server)
    await interaction.followup.send(embed=embed, view=view)


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

bot.run(TOKEN)