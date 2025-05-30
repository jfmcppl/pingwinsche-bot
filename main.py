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

def update_user_gold(user_id, amount, reason):
    if user_id not in bank_data:
        bank_data[user_id] = []
    bank_data[user_id].append({"betrag": amount, "grund": reason})
    save_bank(bank_data)

# --- Events & Commands ---
@bot.event
async def on_ready():
    print(f'🤖 Die Pingwinsche Staatsbank ist online als {bot.user}')
    load_bank()
    start_file_watcher()

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
    os.remove(filename)

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

# --- Casino Commands direkt in main.py ---

@bot.command()
async def coinflip(ctx, bet: int, choice: str = None):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return
    
    if choice is None:
        await ctx.send("Bitte wähle Kopf oder Zahl! Beispiel: `!coinflip 100 Kopf`")
        return
    
    choice = choice.lower()
    if choice not in ["kopf", "zahl"]:
        await ctx.send("Bitte wähle 'Kopf' oder 'Zahl'!")
        return

    result = random.choice(["kopf", "zahl"])
    
    await ctx.send(f"🪙 Die Münze zeigt: **{result.capitalize()}**")

    if result == choice:
        update_user_gold(user_id, bet, "Gewinn beim Coinflip")
        await ctx.send(f"🎉 Du hast gewonnen! Dein Gewinn: {bet} Gold.")
    else:
        update_user_gold(user_id, -bet, "Verlust beim Coinflip")
        await ctx.send(f"😢 Du hast verloren und {bet} Gold verloren.")

@bot.command()
async def slotmachine(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return

    slots = ['🍒', '🍋', '🍊', '🍉', '⭐', '💎']
    result = [random.choice(slots) for _ in range(3)]

    await ctx.send(f"🎰 Ergebnis: {' | '.join(result)}")

    if result[0] == result[1] == result[2]:
        payout = bet * 5
        update_user_gold(user_id, payout, "Gewinn bei Slotmachine (Dreier)")
        await ctx.send(f"🎉 Jackpot! Du gewinnst {payout} Gold!")
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        payout = bet * 2
        update_user_gold(user_id, payout, "Gewinn bei Slotmachine (Zweier)")
        await ctx.send(f"🎉 Du hast zwei Symbole gleich! Gewinn: {payout} Gold.")
    else:
        update_user_gold(user_id, -bet, "Verlust bei Slotmachine")
        await ctx.send(f"Leider kein Gewinn. Du verlierst {bet} Gold.")

@bot.command()
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return

    def card_value(card):
        if card in ['J', 'Q', 'K']:
            return 10
        elif card == 'A':
            return 11
        else:
            return int(card)

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

    # Zeige initiale Karten
    await ctx.send(f"🃏 Deine Karten: {format_hand(player_hand)} (Wert: {hand_value(player_hand)})")
    await ctx.send(f"🃏 Dealer zeigt: {dealer_hand[0]} und eine verdeckte Karte")

    # Prüfe auf Blackjack
    if hand_value(player_hand) == 21:
        if hand_value(dealer_hand) == 21:
            await ctx.send("🃏 Beide haben Blackjack! Unentschieden.")
            return
        else:
            update_user_gold(user_id, int(bet * 1.5), "Blackjack Gewinn")
            await ctx.send(f"🎉 Blackjack! Du gewinnst {int(bet * 1.5)} Gold!")
            return

    # Spieler ist dran - automatische Strategie (vereinfacht)
    while hand_value(player_hand) < 17:
        player_hand.append(deck.pop())
        await ctx.send(f"🃏 Du ziehst: {player_hand[-1]} | Deine Karten: {format_hand(player_hand)} (Wert: {hand_value(player_hand)})")

    player_total = hand_value(player_hand)

    # Prüfe ob Spieler überkauft hat
    if player_total > 21:
        update_user_gold(user_id, -bet, "Verlust bei Blackjack (Bust)")
        await ctx.send(f"💥 Du hast dich überkauft! Du verlierst {bet} Gold.")
        return

    # Dealer ist dran
    await ctx.send(f"🃏 Dealer deckt auf: {format_hand(dealer_hand)} (Wert: {hand_value(dealer_hand)})")

    while hand_value(dealer_hand) < 17:
        dealer_hand.append(deck.pop())
        await ctx.send(f"🃏 Dealer zieht: {dealer_hand[-1]} | Dealer Karten: {format_hand(dealer_hand)} (Wert: {hand_value(dealer_hand)})")

    dealer_total = hand_value(dealer_hand)

    # Bestimme Gewinner
    if dealer_total > 21:
        update_user_gold(user_id, bet, "Gewinn bei Blackjack (Dealer Bust)")
        await ctx.send(f"🎉 Dealer hat sich überkauft! Du gewinnst {bet} Gold!")
    elif player_total > dealer_total:
        update_user_gold(user_id, bet, "Gewinn bei Blackjack")
        await ctx.send(f"🎉 Du gewinnst! Du bekommst {bet} Gold!")
    elif player_total == dealer_total:
        await ctx.send("🤝 Unentschieden! Dein Einsatz wird zurückerstattet.")
    else:
        update_user_gold(user_id, -bet, "Verlust bei Blackjack")
        await ctx.send(f"😞 Dealer gewinnt. Du verlierst {bet} Gold.")

# --- Token laden & Bot starten ---
token = os.getenv('DISCORD_TOKEN')
if not token:
    print("❌ DISCORD_TOKEN nicht gefunden! Bitte füge deinen Token in den Secrets hinzu.")
    exit(1)

bot.run(token)

bot.run(token)

