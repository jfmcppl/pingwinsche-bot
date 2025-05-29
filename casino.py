import discord
from discord.ext import commands
import random
import json
import os

BANK_FILE = 'bank.json'
bank_data = {}

def load_bank():
    global bank_data
    if not os.path.exists(BANK_FILE):
        with open(BANK_FILE, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    try:
        with open(BANK_FILE, 'r', encoding='utf-8') as f:
            bank_data = json.load(f)
    except json.JSONDecodeError:
        bank_data = {}
    return bank_data

def save_bank(data):
    global bank_data
    bank_data = data
    with open(BANK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class Casino(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def casino(self, ctx):
        info = """
🎰 **Willkommen im Pingwinschen Casino!**
Versuche dein Glück:

- `!coinflip <einsatz>` → 50/50 Chance, Einsatz zu verdoppeln
- `!slots <einsatz>` → Gewinne bis zu das 5-fache
"""
        await ctx.send(info)

    @commands.command()
    async def coinflip(self, ctx, einsatz: int):
        user_id = str(ctx.author.id)
        load_bank()
        konto = bank_data.get(user_id, [])
        kontostand = sum(e.get("betrag", 0) for e in konto)

        if einsatz <= 0:
            await ctx.send("❌ Ungültiger Einsatz.")
            return

        if einsatz > kontostand:
            await ctx.send(f"💸 Du hast nicht genug Gold. Kontostand: {kontostand}")
            return

        gewonnen = random.choice([True, False])
        gewinn = einsatz if gewonnen else -einsatz
        ergebnis = "🪙 Kopf! Du hast gewonnen!" if gewonnen else "🪙 Zahl! Du hast verloren."

        bank_data.setdefault(user_id, []).append({
            "betrag": gewinn,
            "grund": "🪙 Coinflip"
        })
        save_bank(bank_data)

        await ctx.send(f"{ergebnis} {'+' if gewinn > 0 else ''}{gewinn} Gold")

    @commands.command()
    async def slots(self, ctx, einsatz: int):
        user_id = str(ctx.author.id)
        load_bank()
        konto = bank_data.get(user_id, [])
        kontostand = sum(e.get("betrag", 0) for e in konto)

        if einsatz <= 0:
            await ctx.send("❌ Ungültiger Einsatz.")
            return

        if einsatz > kontostand:
            await ctx.send(f"💸 Du hast nicht genug Gold. Kontostand: {kontostand}")
            return

        symbole = ["🍒", "🍋", "🍊", "🍉", "⭐", "💎"]
        walzen = [random.choice(symbole) for _ in range(3)]
        gewinn = 0

        if walzen[0] == walzen[1] == walzen[2]:
            gewinn = einsatz * 5
        elif walzen[0] == walzen[1] or walzen[1] == walzen[2] or walzen[0] == walzen[2]:
            gewinn = einsatz * 2
        else:
            gewinn = -einsatz

        bank_data.setdefault(user_id, []).append({
            "betrag": gewinn,
            "grund": "🎰 Slots"
        })
        save_bank(bank_data)

        await ctx.send(f"{' '.join(walzen)} → {'Gewinn' if gewinn > 0 else 'Verlust'}: {abs(gewinn)} Gold")

def setup(bot):
    bot.add_cog(Casino(bot))
