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
async def addgold(ctx, member: str, amount: int, *, grund: str = "Manuelle Änderung"):
    load_bank()
    user_id = member if member == "Casino" else None
    if user_id is None:
        try:
            user_obj = await commands.MemberConverter().convert(ctx, member)
            user_id = str(user_obj.id)
        except commands.BadArgument:
            await ctx.send(f"Benutzer `{member}` wurde nicht gefunden.")
            return
    update_user_gold(user_id, amount, grund)
    await ctx.send(f'{amount} Gold wurde dem Konto von {member} gutgeschrieben. Grund: {grund}')

@bot.command()
async def casino_balance(ctx):
    load_bank()
    casino_gold = get_user_gold("Casino")
    await ctx.send(f"🎲 Das Casino hat aktuell {casino_gold} Gold verfügbar.")

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
    await ctx.send("📤 Ich habe dir die Kontostände per DM geschickt.")
    os.remove(filename)
@bot.command()
async def goldhistory(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    if user_id not in bank_data or not bank_data[user_id]:
        await ctx.send("Du hast keine Einträge in deiner Gold-Historie.")
        return

    all_entries = bank_data[user_id]

    # Gesamtsumme aller Beträge berechnen
    total_gold = sum(e.get("betrag", 0) for e in all_entries)

    # Nur die letzten 10 Einträge anzeigen
    last_entries = all_entries[-10:]

    lines = []
    for entry in last_entries:
        betrag = entry.get("betrag", 0)
        grund = entry.get("grund", "kein Grund angegeben")
        ergebnis = entry.get("ergebnis", "")
        line = f"{betrag:+} Gold — {grund}"
        if ergebnis:
            line += f" | Ergebnis: {ergebnis}"
        lines.append(line)

    # Ausgabe
    response = f"Deine letzten 10 Einträge (Gesamt: {total_gold} Gold):\n" + "\n".join(lines)
    await ctx.send(response)



    filename = f"goldhistory_{user_id}.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    await ctx.author.send(file=discord.File(filename))
    await ctx.message.delete()
    os.remove(filename)

@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

@bot.command()
@casino_channel_only()
async def slotmachine(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    casino_gold = get_user_gold("Casino")

    if casino_gold <= 0:
        await ctx.send("⚠️ Das Casino hat kein Gold mehr und kann keine Spiele anbieten. Bitte warte, bis das Casino wieder aufgefüllt wird.")
        return

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > 10000:
        await ctx.send("⚠️ Der maximale Einsatz beträgt 10.000 Gold.")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return
    if bet > casino_gold:
        await ctx.send("Das Casino hat nicht genug Gold, um deinen Einsatz zu decken.")
        return

    update_user_gold(user_id, -bet, "Einsatz bei Slotmachine")
    update_user_gold("Casino", -bet, f"Slotmachine Einsatz von {ctx.author.name}")

    weighted_slots = ['🍒'] * 5 + ['🍋'] * 5 + ['🍊'] * 4 + ['🍉'] * 3 + ['⭐'] * 2 + ['💎'] * 1
    result = [random.choice(weighted_slots) for _ in range(3)]
    await ctx.send(f"🎰 Ergebnis: {' | '.join(result)}")

    triple_multiplier_map = {'🍒': 3, '🍋': 3.5, '🍊': 4, '🍉': 5, '⭐': 10, '💎': 20}
    double_multiplier_map = {'🍒': 0.7, '🍋': 0.8, '🍊': 0.8, '🍉': 1.0, '⭐': 1.0, '💎': 1.2}

    payout = 0
    if result[0] == result[1] == result[2]:
        payout = int(bet * triple_multiplier_map.get(result[0], 1))
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        symbol = result[1] if result[1] == result[2] else result[0]
        payout = int(bet * double_multiplier_map.get(symbol, 0.5))

    if payout > 0:
        update_user_gold(user_id, payout, "Gewinn bei Slotmachine")
        update_user_gold("Casino", -payout, f"Slotmachine Gewinn an {ctx.author.name}")
        await ctx.send(f"🎉 Du gewinnst {payout} Gold!")
    else:
        await ctx.send("Leider kein Gewinn dieses Mal. Viel Glück beim nächsten Mal!")

@bot.command()
@casino_channel_only()
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    load_bank()
    gold = get_user_gold(user_id)
    casino_gold = get_user_gold("Casino")

    if casino_gold <= 0:
        await ctx.send("⚠️ Das Casino hat kein Gold mehr und kann keine Spiele anbieten. Bitte warte, bis das Casino wieder aufgefüllt wird.")
        return

    if bet <= 0:
        await ctx.send("Bitte setze einen positiven Betrag!")
        return
    if bet > 10000:
        await ctx.send("⚠️ Der maximale Einsatz beträgt 10.000 Gold.")
        return
    if bet > gold:
        await ctx.send("Du hast nicht genug Gold!")
        return
    if bet > casino_gold:
        await ctx.send("Das Casino hat nicht genug Gold, um deinen Einsatz zu decken.")
        return

    update_user_gold(user_id, -bet, "Einsatz bei Blackjack")
    update_user_gold("Casino", bet, f"Blackjack Einsatz von {ctx.author.name}")

    def draw_card():
        cards = [2,3,4,5,6,7,8,9,10,10,10,10,11]
        return random.choice(cards)

    player_cards = [draw_card(), draw_card()]
    dealer_cards = [draw_card(), draw_card()]

    def sum_cards(cards):
        s = sum(cards)
        aces = cards.count(11)
        while s > 21 and aces > 0:
            s -= 10
            aces -= 1
        return s

    player_sum = sum_cards(player_cards)
    dealer_sum = sum_cards(dealer_cards)

    await ctx.send(f"🃏 Deine Karten: {player_cards} (Summe: {player_sum})\n🃏 Dealer-Karten: [{dealer_cards[0]}, ?]")

    while player_sum < 21:
        await ctx.send("Tippe `hit` um eine Karte zu ziehen oder `stand` um zu halten.")
        try:
            def check(m):
                return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["hit", "stand"]
            msg = await bot.wait_for('message', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            await ctx.send("Timeout! Du hast nicht reagiert. Das Spiel wird beendet.")
            update_user_gold(user_id, bet, "Blackjack Einsatz zurück (Timeout)")
            update_user_gold("Casino", -bet, f"Blackjack Einsatz zurück an {ctx.author.name}")
            return

        if msg.content.lower() == "hit":
            card = draw_card()
            player_cards.append(card)
            player_sum = sum_cards(player_cards)
            await ctx.send(f"🃏 Du ziehst eine {card}. Neue Summe: {player_sum}")
            if player_sum > 21:
                await ctx.send(f"💥 Du hast dich überkauft mit {player_sum}. Du verlierst deinen Einsatz.")
                return
        else:
            break

    while dealer_sum < 17:
        dealer_cards.append(draw_card())
        dealer_sum = sum_cards(dealer_cards)

    await ctx.send(f"Dealer Karten: {dealer_cards} (Summe: {dealer_sum})")

    if dealer_sum > 21 or player_sum > dealer_sum:
        payout = bet * 2
        update_user_gold(user_id, payout, "Blackjack Gewinn")
        update_user_gold("Casino", -payout, f"Blackjack Gewinn an {ctx.author.name}")
        await ctx.send(f"🎉 Du gewinnst {payout} Gold!")
    elif player_sum == dealer_sum:
        update_user_gold(user_id, bet, "Blackjack Unentschieden (Einsatz zurück)")
        update_user_gold("Casino", -bet, f"Blackjack Unentschieden Rückzahlung an {ctx.author.name}")
        await ctx.send("🔄 Unentschieden! Dein Einsatz wurde zurückgegeben.")
    else:
        await ctx.send("😢 Der Dealer gewinnt. Du verlierst deinen Einsatz.")
@bot.command()
@commands.has_permissions(administrator=True)
async def cleanbank(ctx):
    load_bank()
    new_bank = {}

    for user_id, entries in bank_data.items():
        if not entries:
            continue
        total = sum(entry.get("betrag", 0) for entry in entries)
        last_10 = entries[-10:]
        new_bank[user_id] = [
            {"betrag": total, "grund": "Gesamtsaldo (bereinigt)"}
        ] + last_10

    save_bank(new_bank)
    load_bank()  # bank_data global aktualisieren
    await ctx.send("✅ bank.json wurde bereinigt: pro Spieler nur noch Summe und letzte 10 Einträge gespeichert.")



# --- Bot Token & Start ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
bot.run(TOKEN)

