import discord
from discord.ext import commands
import random
import json
import os
from flask import Flask
from threading import Thread
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Webserver für UptimeRobot ---
app = Flask('')

@app.route('/')
def home():
    return "Pingwinsche Staatsbank Bot läuft!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# --- Intents aktivieren ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Bankdaten ---
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
            print(f"📊 Bank-Daten geladen: {len(bank_data)} Konten")
    except json.JSONDecodeError:
        print("❌ Fehler beim Lesen der bank.json")
        bank_data = {}

def save_bank(data):
    global bank_data
    bank_data = data
    with open(BANK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class BankFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('bank.json'):
            print("🔄 bank.json wurde geändert - lade Daten neu...")
            time.sleep(0.1)
            load_bank()
            print(f"✅ Neue Bank-Daten: {bank_data}")

def start_file_watcher():
    handler = BankFileHandler()
    observer = Observer()
    observer.schedule(handler, path='.', recursive=False)
    observer.start()
    print("👀 Datei-Überwachung für bank.json gestartet")

# --- Bank-Funktionen ---
def get_user_gold(user_id):
    entries = bank_data.get(user_id, [])
    return sum(entry.get("betrag", 0) for entry in entries)

def update_user_gold(user_id, amount, reason):
    if user_id not in bank_data:
        bank_data[user_id] = []
    bank_data[user_id].append({"betrag": amount, "grund": reason})
    save_bank(bank_data)

# --- Events ---
@bot.event
async def on_ready():
    print(f"🤖 Die Pingwinsche Staatsbank ist online als {bot.user}")
    load_bank()
    start_file_watcher()
    print(f"📌 Registrierte Commands: {list(bot.commands)}")

# --- Standard-Commands ---
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.command()
async def balance(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    try:
        await ctx.author.send(f"{ctx.author.name}, dein Kontostand: {gold} Gold")
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send("Bitte aktiviere DMs für Nachrichten von mir.")

@bot.command()
@commands.has_permissions(administrator=True)
async def addgold(ctx, member: discord.Member, amount: int, *, grund: str = "Manuelle Änderung"):
    user_id = str(member.id)
    load_bank()
    update_user_gold(user_id, amount, grund)
    await ctx.send(f"{amount} Gold wurde {member.display_name} gutgeschrieben. Grund: {grund}")

@bot.command()
async def goldhistory(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    if user_id not in bank_data:
        await ctx.send("Keine Einträge gefunden.")
        return
    lines = []
    total = 0
    for e in bank_data[user_id]:
        total += e["betrag"]
        lines.append(f"{e['betrag']:+} Gold — {e['grund']}")
    lines.append(f"\nGesamt: {total} Gold")
    filename = f"gold_{user_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    await ctx.author.send(file=discord.File(filename))
    await ctx.message.delete()
    os.remove(filename)

# --- Casino: Coinflip mit Hausvorteil ---
@bot.command()
async def coinflip(ctx, bet: int, choice: str = None):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    if bet <= 0 or bet > gold:
        await ctx.send("Ungültiger Einsatz.")
        return
    if choice is None or choice.lower() not in ["kopf", "zahl"]:
        await ctx.send("Nutze: !coinflip <betrag> <kopf|zahl>")
        return

    # Hausvorteil: 49% Gewinnchance
    result = random.choices(["kopf", "zahl"], weights=[49, 49])[0]
    await ctx.send(f"🪙 Die Münze zeigt: **{result.capitalize()}**")

    if result == choice.lower():
        update_user_gold(user_id, bet, "Gewinn beim Coinflip")
        await ctx.send(f"🎉 Du gewinnst {bet} Gold!")
    else:
        update_user_gold(user_id, -bet, "Verlust beim Coinflip")
        await ctx.send(f"😢 Du verlierst {bet} Gold.")

# --- Casino: Slotmachine mit Hausvorteil ---
@bot.command()
async def slotmachine(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    if bet <= 0 or bet > gold:
        await ctx.send("Ungültiger Einsatz.")
        return

    slots = ['🍒', '🍋', '🍊', '🍉', '⭐', '💎']
    result = [random.choice(slots) for _ in range(3)]
    await ctx.send(f"🎰 Ergebnis: {' | '.join(result)}")

    # Hausvorteil: reduzierte Auszahlungsrate
    if result[0] == result[1] == result[2]:
        payout = bet * 4  # statt x5
        update_user_gold(user_id, payout, "Slotmachine Dreier")
        await ctx.send(f"🎉 Jackpot! Gewinn: {payout} Gold")
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        payout = int(bet * 1.5)  # statt x2
        update_user_gold(user_id, payout, "Slotmachine Zweier")
        await ctx.send(f"🎉 Gewinn: {payout} Gold")
    else:
        update_user_gold(user_id, -bet, "Slotmachine Verlust")
        await ctx.send(f"😢 Verlust: {bet} Gold")

# --- Token laden ---
token = os.getenv('DISCORD_TOKEN')
if not token:
    print("❌ Kein DISCORD_TOKEN gefunden!")
    exit(1)

bot.run(token)
