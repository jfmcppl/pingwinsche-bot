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

# --- Webserver-Setup für UptimeRobot ---
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

# --- Bot initialisieren ---
bot = commands.Bot(command_prefix='!', intents=intents)

# --- Bank-Datei & Daten ---
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

# --- Dateiüberwachung für bank.json ---
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

# --- Bank-Hilfsfunktionen ---
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

# --- Channel-ID für Casino-Befehle ---
ALLOWED_CHANNEL_ID = 1377775929249497159

def casino_channel_only():
    def predicate(ctx):
        return ctx.channel.id == ALLOWED_CHANNEL_ID
    return commands.check(predicate)

# --- Events & Commands ---
@bot.event
async def on_ready():
    print(f'🤖 Die Pingwinsche Staatsbank ist online als {bot.user}')
    load_bank()
    start_file_watcher()
    print(f"📌 Registrierte Commands: {list(bot.commands)}")

@bot.command()
async def balance(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    total_gold = get_user_gold(user_id)
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
    update_user_gold(user_id, amount, grund)
    await ctx.send(f'{amount} Gold wurde dem Konto von {member.display_name} gutgeschrieben. Grund: {grund}')

@bot.command()
@commands.has_permissions(administrator=True)
async def backupbank(ctx):
    try:
        await ctx.author.send(file=discord.File('bank.json'))
        await ctx.send(f"{ctx.author.mention}, ich habe dir die aktuelle bank.json per DM geschickt.")
    except Exception as e:
        await ctx.send(f"Fehler beim Senden der Datei: {e}")

@bot.command()
@commands.has_permissions(administrator=True)
async def allbalances(ctx):
    load_bank()
    if not bank_data:
        await ctx.send("Keine Konten gefunden.")
        return

    lines = []
    for user_id, eintraege in bank_data.items():
        try:
            member = await ctx.guild.fetch_member(int(user_id))
            name = member.display_name
        except:
            name = f"Unbekannt ({user_id})"
        saldo = sum(e.get("betrag", 0) for e in eintraege)
        lines.append(f"{name}: {saldo} Gold")

    text = "\n".join(lines)
    filename = "allbalances.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(text)

    await ctx.author.send(file=discord.File(filename))
    await ctx.send("\ud83d\udce4 Ich habe dir die Kontostände per DM geschickt.")
    os.remove(filename)

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
        ergebnis = entry.get("ergebnis", "")
        gesamt += betrag
        line = f"{betrag:+} Gold — {grund}"
        if ergebnis:
            line += f" | Ergebnis: {ergebnis}"
        lines.append(line)

    lines.append(f"\nGesamt: {gesamt} Gold")

    filename = f"goldhistory_{user_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    await ctx.author.send(file=discord.File(filename))
    await ctx.message.delete()
    os.remove(filename)

@bot.command()
async def ping(ctx):
    await ctx.send("\ud83c\udfd3 Pong!")

@bot.command()
@casino_channel_only()
async def slotmachine(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > 10000:
        await ctx.send("⚠️ Der maximale Einsatz beträgt 10.000 Gold.")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return

    update_user_gold(user_id, -bet, "Einsatz bei Slotmachine")

    weighted_slots = ['🍒'] * 5 + ['🍋'] * 5 + ['🍊'] * 4 + ['🍉'] * 3 + ['⭐'] * 2 + ['💎'] * 1
    result = [random.choice(weighted_slots) for _ in range(3)]
    await ctx.send(f"🎰 Ergebnis: {' | '.join(result)}")

    triple_multiplier_map = {'🍒': 3, '🍋': 3.5, '🍊': 4, '🍉': 5, '⭐': 10, '💎': 20}
    double_multiplier_map = {'🍒': 0.7, '🍋': 0.8, '🍊': 0.8, '🍉': 1.0, '⭐': 1.0, '💎': 1.2}

    if result[0] == result[1] == result[2]:
        symbol = result[0]
        payout = int(bet * triple_multiplier_map.get(symbol, 3))
        update_user_gold(user_id, payout, f"Slot-Gewinn (Dreifach {symbol})")
        await ctx.send(f"🎉 Jackpot mit {symbol}! Du gewinnst {payout} Gold.")
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        symbol = result[0] if result[0] == result[1] or result[0] == result[2] else result[1]
        payout = int(bet * double_multiplier_map.get(symbol, 0.5))
        update_user_gold(user_id, payout, f"Kleingewinn bei Slotmachine (Zweifach {symbol})")
        await ctx.send(f"✨ Zwei Symbole gleich ({symbol})! Du bekommst {payout} Gold zurück.")
    else:
        await ctx.send(f"😢 Kein Gewinn. Du verlierst deinen Einsatz von {bet} Gold.")

@bot.command()
@casino_channel_only()
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > 10000:
        await ctx.send("⚠️ Der maximale Einsatz beträgt 10.000 Gold.")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return

    update_user_gold(user_id, -bet, "Einsatz bei Blackjack", result="Einsatz")

    def card_value(card):
        return 10 if card in ['J', 'Q', 'K'] else 11 if card == 'A' else int(card)

    def hand_value(hand):
        value = sum(card_value(card) for card in hand)
        aces = hand.count('A')
        while value > 21 and aces:
            value -= 10
            aces -= 1
        return value

    def format_hand(hand):
        return ', '.join(hand)

    deck = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'] * 4
    random.shuffle(deck)

    player_hand = [deck.pop(), deck.pop()]
    dealer_hand = [deck.pop(), deck.pop()]

    await ctx.send(f"Deine Karten: {format_hand(player_hand)} (Wert: {hand_value(player_hand)})")
    await ctx.send(f"Dealer zeigt: {dealer_hand[0]}")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["hit", "stand"]

    while True:
        await ctx.send("Willst du noch eine Karte? Tippe `hit` oder `stand`.")
        try:
            msg = await bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            await ctx.send("Zeit abgelaufen, Spiel beendet.")
            update_user_gold(user_id, 0, "Blackjack Timeout", result="Verlust")
            return

        if msg.content.lower() == "hit":
            player_hand.append(deck.pop())
            await ctx.send(f"Deine Karten: {format_hand(player_hand)} (Wert: {hand_value(player_hand)})")
            if hand_value(player_hand) > 21:
                update_user_gold(user_id, 0, "Verlust bei Blackjack (Bust)", result="Verlust")
                await ctx.send("Du hast überkauft! Du verlierst.")
                return
        else:
            break

    while hand_value(dealer_hand) < 17:
        dealer_hand.append(deck.pop())
    await ctx.send(f"Dealer Karten: {format_hand(dealer_hand)} (Wert: {hand_value(dealer_hand)})")

    player_score = hand_value(player_hand)
    dealer_score = hand_value(dealer_hand)

    if dealer_score > 21 or player_score > dealer_score:
        payout = int(bet * 1.9)
        update_user_gold(user_id, payout, "Gewinn bei Blackjack", result="Gewinn")
        await ctx.send(f"🎉 Du gewinnst! {payout} Gold.")
    elif player_score == dealer_score:
        update_user_gold(user_id, bet, "Rückzahlung bei Unentschieden (Blackjack)", result="Unentschieden")
        await ctx.send("Unentschieden! Dein Einsatz wird zurückerstattet.")
    else:
        update_user_gold(user_id, 0, "Verlust bei Blackjack", result="Verlust")
        await ctx.send(f"Du verlierst {bet} Gold.")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send(f"❌ Dieser Befehl ist nur im Casino-Channel erlaubt! (Channel-ID: {ALLOWED_CHANNEL_ID})")
    else:
        raise error

bot.run(os.getenv('DISCORD_TOKEN'))
