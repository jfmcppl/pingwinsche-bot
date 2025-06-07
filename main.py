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
import asyncio

# --- Webserver für UptimeRobot (halt Bot am Laufen) ---
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

# --- Discord Intents ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# --- Bot Setup ---
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Bank System ---
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
        print("❌ Fehler beim Lesen der bank.json - leere Bank wird genutzt")
        bank_data = {}
    return bank_data

def save_bank(data):
    global bank_data
    bank_data = data
    with open(BANK_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- Filewatcher für bank.json ---
class BankFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('bank.json') and not event.is_directory:
            print("🔄 bank.json wurde geändert - lade neu...")
            time.sleep(0.1)  # Warte kurz, bis Datei stabil ist
            load_bank()
            print(f"✅ Bank-Daten aktualisiert: {len(bank_data)} Konten")

def start_file_watcher():
    event_handler = BankFileHandler()
    observer = Observer()
    observer.schedule(event_handler, path='.', recursive=False)
    observer.start()
    print("👀 Datei-Überwachung gestartet")
    return observer

# --- Bank Hilfsfunktionen ---
def get_user_gold(user_id):
    entries = bank_data.get(user_id, [])
    if isinstance(entries, list):
        return sum(entry.get("betrag", 0) for entry in entries)
    return 0

def update_user_gold(user_id, amount, reason, result=None):
    if user_id not in bank_data:
        bank_data[user_id] = []
    entry = {"betrag": amount, "grund": reason}
    if result is not None:
        entry["ergebnis"] = result
    bank_data[user_id].append(entry)
    save_bank(bank_data)

# --- Channel-Check für Casino Commands ---
ALLOWED_CHANNEL_ID = 1377775929249497159

def casino_channel_only():
    def predicate(ctx):
        return ctx.channel.id == ALLOWED_CHANNEL_ID
    return commands.check(predicate)

# --- Event: Bot Start ---
@bot.event
async def on_ready():
    print(f"🤖 Pingwinsche Staatsbank Bot online als {bot.user}")
    load_bank()
    start_file_watcher()
    print(f"📌 Befehle geladen: {list(bot.commands)}")

# --- Commands ---

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.command()
@casino_channel_only()
async def balance(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    await ctx.send(f"💰 {ctx.author.mention}, dein Kontostand beträgt {gold} Gold.")

@bot.command()
@casino_channel_only()
async def deposit(ctx, amount: int):
    if amount <= 0:
        await ctx.send("Bitte gib einen positiven Betrag zum Einzahlen an.")
        return
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    if amount > gold:
        await ctx.send("Du hast nicht genug Gold zum Einzahlen.")
        return
    update_user_gold(user_id, -amount, "Einzahlung ins Casino")
    update_user_gold("Casino", amount, f"Einzahlung von {ctx.author.name}")
    await ctx.send(f"✅ {amount} Gold wurden ins Casino eingezahlt.")

@bot.command()
@casino_channel_only()
async def withdraw(ctx, amount: int):
    if amount <= 0:
        await ctx.send("Bitte gib einen positiven Betrag zum Abheben an.")
        return
    user_id = str(ctx.author.id)
    load_bank()
    casino_gold = get_user_gold("Casino")
    if amount > casino_gold:
        await ctx.send("Das Casino hat nicht genug Gold, um diesen Betrag auszuzahlen.")
        return
    update_user_gold("Casino", -amount, f"Auszahlung an {ctx.author.name}")
    update_user_gold(user_id, amount, "Auszahlung aus dem Casino")
    await ctx.send(f"✅ {amount} Gold wurden ausgezahlt.")

@bot.command()
@casino_channel_only()
async def slotmachine(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    user_gold = get_user_gold(user_id)
    casino_gold = get_user_gold("Casino")

    if casino_gold <= 0:
        await ctx.send("⚠️ Das Casino hat kein Gold mehr.")
        return

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > 5000:
        await ctx.send("⚠️ Maximaler Einsatz: 5.000 Gold.")
        return
    if bet > user_gold:
        await ctx.send("Du hast nicht genug Gold.")
        return
    if bet > casino_gold:
        await ctx.send("Das Casino kann deinen Einsatz nicht decken.")
        return

    steuer_prozent = 10
    steuer = int(bet * steuer_prozent / 100)
    netto_bet = bet - steuer

    # Steuer und Einsatz buchen
    update_user_gold(user_id, -steuer, f"{steuer_prozent}% Steuer Slotmachine")
    update_user_gold("Casino", steuer, f"Steuer von {ctx.author.name} (Slotmachine)")
    update_user_gold(user_id, -netto_bet, "Einsatz Slotmachine")
    update_user_gold("Casino", -netto_bet, f"Einsatz von {ctx.author.name} (Slotmachine)")

    weighted_slots = ['🍒'] * 5 + ['🍋'] * 5 + ['🍊'] * 4 + ['🍉'] * 3 + ['⭐'] * 2 + ['💎'] * 1
    result = [random.choice(weighted_slots) for _ in range(3)]
    await ctx.send(f"🎰 Ergebnis: {' | '.join(result)}")

    triple_multiplier_map = {'🍒': 3, '🍋': 3.5, '🍊': 4, '🍉': 5, '⭐': 10, '💎': 20}
    double_multiplier_map = {'🍒': 0.7, '🍋': 0.8, '🍊': 0.8, '🍉': 1.0, '⭐': 1.0, '💎': 1.2}

    payout = 0
    if result[0] == result[1] == result[2]:
        payout = int(netto_bet * triple_multiplier_map.get(result[0], 1))
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        symbol = None
        if result[0] == result[1]:
            symbol = result[0]
        elif result[1] == result[2]:
            symbol = result[1]
        else:
            symbol = result[0]
        payout = int(netto_bet * double_multiplier_map.get(symbol, 0.5))

    if payout > 0:
        update_user_gold(user_id, payout, "Gewinn Slotmachine")
        update_user_gold("Casino", -payout, f"Slotmachine Gewinn an {ctx.author.name}")
        await ctx.send(f"🎉 Du gewinnst {payout} Gold!")
    else:
        await ctx.send("Leider kein Gewinn, viel Glück beim nächsten Mal!")

# Beispiel Blackjack (vereinfacht)
@bot.command()
@casino_channel_only()
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    user_gold = get_user_gold(user_id)
    casino_gold = get_user_gold("Casino")

    if casino_gold <= 0:
        await ctx.send("⚠️ Das Casino hat kein Gold mehr.")
        return

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > 10000:
        await ctx.send("⚠️ Maximaler Einsatz bei Blackjack: 10.000 Gold.")
        return
    if bet > user_gold:
        await ctx.send("Du hast nicht genug Gold.")
        return
    if bet > casino_gold:
        await ctx.send("Das Casino kann deinen Einsatz nicht decken.")
        return

    steuer_prozent = 10
    steuer = int(bet * steuer_prozent / 100)
    netto_bet = bet - steuer

    update_user_gold(user_id, -steuer, f"{steuer_prozent}% Steuer Blackjack")
    update_user_gold("Casino", steuer, f"Steuer von {ctx.author.name} (Blackjack)")
    update_user_gold(user_id, -netto_bet, "Einsatz Blackjack")
    update_user_gold("Casino", -netto_bet, f"Einsatz von {ctx.author.name} (Blackjack)")

    # Simples Blackjack-Ergebnis (50% Chance gewinnen, 50% verlieren)
    await ctx.send(f"🃏 Blackjack startet mit Einsatz {bet} Gold...")

    await asyncio.sleep(2)  # Spannung aufbauen

    win = random.choice([True, False])
    if win:
        payout = netto_bet * 2
        update_user_gold(user_id, payout, "Gewinn Blackjack")
        update_user_gold("Casino", -payout, f"Blackjack Gewinn an {ctx.author.name}")
        await ctx.send(f"🎉 Du gewinnst {payout} Gold beim Blackjack!")
    else:
        await ctx.send("😞 Leider verloren beim Blackjack. Viel Glück beim nächsten Mal!")

# Weitere Commands und Features können hier ergänzt werden...

# --- Bot Token & Start ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)
