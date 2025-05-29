import discord
from discord.ext import commands
import json
import os
from flask import Flask
from threading import Thread
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Webserver-Setup für UptimeRobot
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

# Intents aktivieren, damit der Bot Nachrichten lesen und Mitglieder-Daten bekommt
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

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
        print("❌ Fehler beim Lesen der bank.json - verwende leere Bank")
        bank_data = {}
    return bank_data

def save_bank(data):
    global bank_data
    bank_data = data
    with open(BANK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

class BankFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('bank.json') and not event.is_directory:
            print("🔄 bank.json wurde geändert - lade Daten neu...")
            time.sleep(0.1)
            load_bank()
            print(f"✅ Neue Bank-Daten: {bank_data}")

def start_file_watcher():
    event_handler = BankFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    print("👀 Datei-Überwachung für bank.json gestartet")
    return observer

@bot.event
async def on_ready():
    print(f'🤖 Die Pingwinsche Staatsbank ist online als {bot.user}')
    load_bank()
    start_file_watcher()

@bot.command()
async def balance(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    gold_entries = bank_data.get(user_id, [])
    if isinstance(gold_entries, list):
        total_gold = sum(entry.get("betrag", 0) for entry in gold_entries)
    else:
        total_gold = 0
    try:
        await ctx.author.send(f'{ctx.author.name}, dein Kontostand beträgt {total_gold} Gold.')
        await ctx.message.delete()
    except discord.Forbidden:
        await ctx.send(f"{ctx.author.mention}, ich kann dir keine Direktnachricht schicken. Bitte aktiviere DMs von Servermitgliedern.")

@bot.command()
@commands.has_permissions(administrator=True)
async def addgold(ctx, member: discord.Member, amount: int, *, grund: str = "Manuelle Änderung"):
    user_id = str(member.id)
    load_bank()
    if user_id not in bank_data:
        bank_data[user_id] = []
    bank_data[user_id].append({"betrag": amount, "grund": grund})
    save_bank(bank_data)
    await ctx.send(f'{amount} Gold wurde dem Konto von {member.display_name} gutgeschrieben. Grund: {grund}')

@bot.command()
async def goldhistory(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    if user_id not in bank_data or not bank_data[user_id]:
        await ctx.send("Du hast keine Einträge in deiner Gold-Historie.")
        return

    lines = []
    gesamt = 0
    for entry in bank_data[user_id]:
        betrag = entry.get("betrag", 0)
        grund = entry.get("grund", "kein Grund angegeben")
        gesamt += betrag
        lines.append(f"{betrag:+} Gold — {grund}")

    lines.append(f"\nGesamt: {gesamt} Gold")

    filename = f"goldhistory_{user_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    await ctx.author.send(file=discord.File(filename))
    await ctx.message.delete()

    import os
    os.remove(filename)

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

token = os.getenv('DISCORD_TOKEN')
if not token:
    print("❌ DISCORD_TOKEN nicht gefunden! Bitte füge deinen Token in den Secrets hinzu.")
    exit(1)

bot.run(token)

