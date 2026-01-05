import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from db import db

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")

if not DISCORD_TOKEN:
    raise RuntimeError("Please set DISCORD_TOKEN in your environment or .env file")

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


class RedeemModal(discord.ui.Modal, title="Redeem Invoice"):
    invoice_id = discord.ui.TextInput(label="Invoice ID", placeholder="Enter your invoice ID here")

    def __init__(self, db_instance, view: discord.ui.View):
        super().__init__()
        self.db = db_instance
        self.view = view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        invoice_id = self.invoice_id.value.strip()
        user = interaction.user
        result = self.db.bind_invoice(invoice_id, user.id, f"{user.name}#{user.discriminator}")
        if not result.get("ok"):
            if result.get("error") == "not_found":
                await interaction.response.send_message("Invoice ID not found.", ephemeral=True)
                return
            if result.get("error") == "already_bound":
                inv = result.get("invoice")
                await interaction.response.send_message(
                    f"Invoice already bound to {inv.get('bound_username')} on {inv.get('bound_at')}", ephemeral=True
                )
                return
        invoice = result.get("invoice")

        # Assign or create Buyer role
        guild = interaction.guild
        role_name = "Buyer"
        role = discord.utils.get(guild.roles, name=role_name)
        try:
            if role is None:
                role = await guild.create_role(name=role_name)
        except Exception:
            await interaction.response.send_message(
                "Failed to create or assign role. Ensure the bot has Manage Roles permission.", ephemeral=True
            )
            return

        try:
            member = guild.get_member(user.id)
            if member is None:
                member = await guild.fetch_member(user.id)
            await member.add_roles(role, reason="Redeemed invoice")
        except Exception:
            await interaction.response.send_message(
                "Failed to assign role. Ensure the bot's role is high enough and has Manage Roles.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"Success! Invoice redeemed and role '{role.name}' assigned. Admins can view invoice details.", ephemeral=True
        )


class RedeemView(discord.ui.View):
    def __init__(self, db_instance):
        super().__init__(timeout=None)
        self.db = db_instance

    @discord.ui.button(label="Redeem Invoice", style=discord.ButtonStyle.blurple, custom_id="redeem_invoice_button")
    async def redeem_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = RedeemModal(self.db, self)
        await interaction.response.send_modal(modal)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    if GUILD_ID:
        try:
            guild = discord.Object(id=int(GUILD_ID))
            await bot.tree.sync(guild=guild)
            print(f"Synced commands to guild {GUILD_ID}")
        except Exception as e:
            print("Failed to sync to guild:", e)
    else:
        try:
            await bot.tree.sync()
            print("Synced global commands (may take up to an hour to appear)")
        except Exception as e:
            print("Failed to sync global commands:", e)


def is_guild_admin(interaction: discord.Interaction) -> bool:
    return interaction.user and interaction.user.guild_permissions.manage_guild


@bot.tree.command(name="create_invoice", description="Create a new invoice (admin)")
@app_commands.describe(invoice_id="Invoice ID to create", key="License key or SKU")
async def create_invoice(interaction: discord.Interaction, invoice_id: str, key: str):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    ok = db.create_invoice(invoice_id, key)
    if ok:
        await interaction.response.send_message(f"Invoice {invoice_id} created.", ephemeral=True)
    else:
        await interaction.response.send_message(f"Invoice {invoice_id} already exists.", ephemeral=True)


@bot.tree.command(name="post_redeem_message", description="Post a redeem message with a button")
async def post_redeem_message(interaction: discord.Interaction):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    view = RedeemView(db)
    await interaction.channel.send("Click to redeem your invoice and receive the Buyer role:", view=view)
    await interaction.response.send_message("Redeem message posted.", ephemeral=True)


@bot.tree.command(name="invoice_info", description="Show invoice info (admin)")
@app_commands.describe(invoice_id="Invoice ID to look up")
async def invoice_info(interaction: discord.Interaction, invoice_id: str):
    if not is_guild_admin(interaction):
        await interaction.response.send_message("You are not allowed to use this command.", ephemeral=True)
        return
    inv = db.get_invoice(invoice_id)
    if not inv:
        await interaction.response.send_message("Invoice not found.", ephemeral=True)
        return
    lines = [
        f"Invoice ID: {inv.get('invoice_id')}",
        f"Created at (UTC): {inv.get('created_at')}",
        f"Key: {inv.get('key')}",
        f"Bound user: {inv.get('bound_username') or 'Not bound'}",
        f"Bound at: {inv.get('bound_at') or 'N/A'}",
    ]
    await interaction.response.send_message("\\n".join(lines), ephemeral=True)


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
