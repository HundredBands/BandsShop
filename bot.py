import os
from dotenv import load_dotenv
import discord
from discord import app_commands
from discord.ext import commands
from db import db
from keep_alive import keep_alive

# Load env
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing in .env")

keep_alive()  # Start web server

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------- EMBED HELPER ----------------
def create_embed(title,
                 description="",
                 color=discord.Color.blue(),
                 user=None,
                 fields=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if user:
        embed.set_footer(text=f"Requested by {user}", icon_url=user.avatar.url)
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    return embed


# ---------------- MODALS ----------------
class RedeemModal(discord.ui.Modal, title="Redeem Invoice"):
    invoice_id = discord.ui.TextInput(label="Invoice ID",
                                      placeholder="Enter your invoice ID here")

    def __init__(self, db_instance):
        super().__init__()
        self.db = db_instance

    async def on_submit(self, interaction: discord.Interaction):
        invoice_id = self.invoice_id.value.strip()
        user = interaction.user
        result = self.db.bind_invoice(invoice_id, user.id,
                                      f"{user.name}#{user.discriminator}")
        if not result.get("ok"):
            error = result.get("error")
            if error == "not_found":
                embed = create_embed("Error ❌",
                                     "Invoice ID not found.",
                                     color=discord.Color.red(),
                                     user=user)
            else:
                inv = result.get("invoice")
                embed = create_embed(
                    "Invoice Already Redeemed ⚠️",
                    f"Invoice already bound to **{inv['bound_username']}** on {inv['bound_at']}",
                    color=discord.Color.orange(),
                    user=user)
            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)
            return

        # Assign Buyer role
        guild = interaction.guild
        role_name = "Buyer"
        role = discord.utils.get(guild.roles, name=role_name)
        if not role:
            role = await guild.create_role(name=role_name)
        member = guild.get_member(user.id) or await guild.fetch_member(user.id)
        await member.add_roles(role, reason="Redeemed invoice")

        embed = create_embed("Success ✅",
                             f"Invoice redeemed! Role '{role.name}' assigned.",
                             color=discord.Color.green(),
                             user=user)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------- VIEWS ----------------
class RedeemView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

        # URL Button for purchase
        self.add_item(
            discord.ui.Button(label="Purchase",
                              style=discord.ButtonStyle.link,
                              url="https://your-purchase-link.com"))

    # Redeem modal button
    @discord.ui.button(label="Redeem Invoice",
                       style=discord.ButtonStyle.blurple)
    async def redeem(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        modal = RedeemModal(db)
        await interaction.response.send_modal(modal)

    # Status button
    @discord.ui.button(label="Status", style=discord.ButtonStyle.gray)
    async def status(self, interaction: discord.Interaction,
                     button: discord.ui.Button):
        user = interaction.user
        invoices = db.list_invoices()
        found = None
        for inv in invoices:
            if inv[2] == f"{user.name}#{user.discriminator}":
                found = inv
                break
        if not found:
            embed = create_embed("No Invoice ❌",
                                 "You have not redeemed any invoice.",
                                 color=discord.Color.red(),
                                 user=user)
        else:
            embed = create_embed(f"My Invoice: {found[0]}",
                                 color=discord.Color.blurple(),
                                 user=user,
                                 fields=[("Key", found[1], False),
                                         ("Bound At", found[3], False),
                                         ("Created At", found[4], False)])
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # User-Management button
    @discord.ui.button(label="User-Management", style=discord.ButtonStyle.red)
    async def user_management(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_guild:
            embed = create_embed("Permission Denied ❌",
                                 "You cannot access user management.",
                                 color=discord.Color.red(),
                                 user=interaction.user)
        else:
            embed = create_embed(
                "User Management ⚙️",
                "Use `/update_invoice`, `/delete_invoice`, `/list_invoices` for admin tasks.",
                color=discord.Color.orange(),
                user=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------- UTILITY ----------------
def is_guild_admin(interaction):
    return interaction.user.guild_permissions.manage_guild


# ---------------- EVENTS ----------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await bot.tree.sync()  # Sync globally
    print("Commands synced globally")


# ---------------- COMMANDS ----------------
# Admin: create invoice
@bot.tree.command(name="create_invoice", description="Create a new invoice")
@app_commands.describe(invoice_id="Invoice ID", key="License key")
async def create_invoice(interaction: discord.Interaction, invoice_id: str,
                         key: str):
    if not is_guild_admin(interaction):
        embed = create_embed("Permission Denied ❌",
                             "You cannot use this command.",
                             color=discord.Color.red(),
                             user=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if db.create_invoice(invoice_id, key):
        embed = create_embed("Invoice Created ✅",
                             f"Invoice **{invoice_id}** created.",
                             color=discord.Color.green(),
                             user=interaction.user)
    else:
        embed = create_embed("Error ❌",
                             f"Invoice **{invoice_id}** already exists.",
                             color=discord.Color.red(),
                             user=interaction.user)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Admin: delete invoice
@bot.tree.command(name="delete_invoice", description="Delete an invoice")
@app_commands.describe(invoice_id="Invoice ID")
async def delete_invoice(interaction: discord.Interaction, invoice_id: str):
    if not is_guild_admin(interaction):
        embed = create_embed("Permission Denied ❌",
                             "You cannot use this command.",
                             color=discord.Color.red(),
                             user=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if db.delete_invoice(invoice_id):
        embed = create_embed("Invoice Deleted ✅",
                             f"Invoice {invoice_id} removed.",
                             color=discord.Color.green(),
                             user=interaction.user)
    else:
        embed = create_embed("Error ❌",
                             "Invoice not found.",
                             color=discord.Color.red(),
                             user=interaction.user)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Admin: update invoice key
@bot.tree.command(name="update_invoice", description="Update invoice key")
@app_commands.describe(invoice_id="Invoice ID", key="New key")
async def update_invoice(interaction: discord.Interaction, invoice_id: str,
                         key: str):
    if not is_guild_admin(interaction):
        embed = create_embed("Permission Denied ❌",
                             "You cannot use this command.",
                             color=discord.Color.red(),
                             user=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if db.update_invoice(invoice_id, key):
        embed = create_embed("Invoice Updated ✅",
                             f"Invoice {invoice_id} key updated.",
                             color=discord.Color.green(),
                             user=interaction.user)
    else:
        embed = create_embed("Error ❌",
                             "Invoice not found.",
                             color=discord.Color.red(),
                             user=interaction.user)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Admin: list invoices
@bot.tree.command(name="list_invoices", description="List all invoices")
async def list_invoices(interaction: discord.Interaction):
    if not is_guild_admin(interaction):
        embed = create_embed("Permission Denied ❌",
                             "You cannot use this command.",
                             color=discord.Color.red(),
                             user=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    invoices = db.list_invoices()
    desc = ""
    for inv in invoices:
        desc += f"**{inv[0]}** | Key: {inv[1]} | Bound: {inv[2] or 'No'}\n"
    if not desc:
        desc = "No invoices yet."
    embed = create_embed("All Invoices 📄",
                         desc,
                         color=discord.Color.blurple(),
                         user=interaction.user)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# User: my invoice
@bot.tree.command(name="my_invoice", description="See your redeemed invoice")
async def my_invoice(interaction: discord.Interaction):
    user = interaction.user
    invoices = db.list_invoices()
    found = None
    for inv in invoices:
        if inv[2] == f"{user.name}#{user.discriminator}":
            found = inv
            break
    if not found:
        embed = create_embed("No Invoice ❌",
                             "You have not redeemed any invoice.",
                             color=discord.Color.red(),
                             user=user)
    else:
        embed = create_embed(f"My Invoice: {found[0]}",
                             color=discord.Color.blurple(),
                             user=user,
                             fields=[("Key", found[1], False),
                                     ("Bound At", found[3], False),
                                     ("Created At", found[4], False)])
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Post redeem embed with buttons
@bot.tree.command(name="post_redeem_message",
                  description="Post redeem message with buttons")
async def post_redeem_message(interaction: discord.Interaction):
    if not is_guild_admin(interaction):
        embed = create_embed("Permission Denied ❌",
                             "You cannot use this command.",
                             color=discord.Color.red(),
                             user=interaction.user)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    embed = create_embed(
        "Redeem Your Invoice 💳",
        "Click **Redeem Invoice** to claim your role!\nUse **Status** to check your invoice.\n**Purchase** for purchasing info.\n**User-Management** for admin tasks.",
        color=discord.Color.green())
    view = RedeemView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("Redeem message posted!",
                                            ephemeral=True)


# ---------------- RUN ----------------
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
