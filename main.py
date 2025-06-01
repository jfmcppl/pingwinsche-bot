import discord
from discord.ext import commands
import json
import os
import random
import asyncio

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

BANK_FILE = "bank.json"
ALLOWED_CHANNEL_ID = 123456789012345678  # Setze hier deine Casino-Channel-ID ein
CASINO_ACCOUNT = "Casino"

bank_data = {}

def load_bank():
    global bank_data
    if os.path.exists(BANK_FILE):
        with open(BANK_FILE, "r", encoding="utf-8") as f:
            bank_data = json.load(f)
    else:
        bank_data = {}

def save_bank():
    with open(BANK_FILE, "w", encoding="utf-8") as f:
        json.dump(bank_data, f, ensure_ascii=False, indent=4)

def get_user_gold(user_id):
    load_bank()
    return sum(entry.get("betrag", 0) for entry in bank_data.get(str(user_id), []))

def update_user_gold(user_id, amount, reason="Unbekannter Grund", result=""):
    user_id = str(user_id)
    load_bank()
    if user_id not in bank_data:
        bank_data[user_id] = []
    bank_data[user_id].append({"betrag": amount, "grund": reason, "ergebnis": result})
    save_bank()

def get_casino_gold():
    return get_user_gold(CASINO_ACCOUNT)

def casino_channel_only():
    def predicate(ctx):
        return ctx.channel.id == ALLOWED_CHANNEL_ID
    return commands.check(predicate)

@bot.event
async def on_ready():
    print(f"Bot ist eingeloggt als {bot.user}")

@bot.command()
async def balance(ctx):
    user_id = ctx.author.id
    gold = get_user_gold(user_id)
    await ctx.send(f"{ctx.author.mention}, du hast aktuell {gold} Gold.")

@bot.command()
@commands.has_permissions(administrator=True)
async def addgold(ctx, member: str, amount: int, *, grund: str = "Manuelle Änderung"):
    user_id = None
    if member.lower() == "casino":
        user_id = CASINO_ACCOUNT
    else:
        try:
            user_id = str((await commands.MemberConverter().convert(ctx, member)).id)
        except:
            await ctx.send(f"Fehler: Benutzer '{member}' nicht gefunden und nicht 'Casino'.")
            return
    update_user_gold(user_id, amount, grund)
    await ctx.send(f"{amount} Gold wurde dem Konto von {member} gutgeschrieben. Grund: {grund}")

@bot.command()
@commands.has_permissions(administrator=True)
async def backupbank(ctx):
    if os.path.exists(BANK_FILE):
        await ctx.author.send(file=discord.File(BANK_FILE))
        await ctx.send("Bank-Backup wurde dir per DM gesendet.")
    else:
        await ctx.send("Bank-Datei existiert noch nicht.")

@bot.command()
@commands.has_permissions(administrator=True)
async def allbalances(ctx):
    load_bank()
    lines = []
    for user_id, entries in bank_data.items():
        total = sum(entry.get("betrag", 0) for entry in entries)
        lines.append(f"{user_id}: {total} Gold")
    message = "\n".join(lines) if lines else "Keine Kontostände vorhanden."
    # Wegen möglicher Länge sende als Datei
    filename = "allbalances.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(message)
    await ctx.author.send(file=discord.File(filename))
    os.remove(filename)
    await ctx.send("Alle Kontostände wurden dir per DM gesendet.")

@bot.command()
async def goldhistory(ctx):
    user_id = str(ctx.author.id)
    load_bank()
    if user_id not in bank_data or not bank_data[user_id]:
        await ctx.send("Du hast keine Einträge in deiner Gold-Historie.")
        return

    all_entries = bank_data[user_id]
    gesamt = sum(entry.get("betrag", 0) for entry in all_entries)
    last_10 = all_entries[-10:]

    lines = []
    for entry in last_10:
        betrag = entry.get("betrag", 0)
        grund = entry.get("grund", "kein Grund angegeben")
        ergebnis = entry.get("ergebnis", "")
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
async def casino_balance(ctx):
    gold = get_casino_gold()
    await ctx.send(f"🎰 Das Casino hat aktuell {gold} Gold zur Verfügung.")

@bot.command()
@casino_channel_only()
async def slotmachine(ctx, bet: int):
    user_id = str(ctx.author.id)
    gold = get_user_gold(user_id)
    casino_gold = get_casino_gold()

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
        await ctx.send("Das Casino hat nicht genug Gold, um deinen Einsatz zu decken. Bitte versuche es später erneut.")
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
        update_user_gold(CASINO_ACCOUNT, -payout, f"Slot-Auszahlung (Dreifach {symbol})")
        update_user_gold(user_id, payout, f"Slot-Gewinn (Dreifach {symbol})")
        await ctx.send(f"🎉 Jackpot mit {symbol}! Du gewinnst {payout} Gold.")
    elif result[0] == result[1] or result[1] == result[2] or result[0] == result[2]:
        symbol = result[0] if result[0] == result[1] or result[0] == result[2] else result[1]
        payout = int(bet * double_multiplier_map.get(symbol, 0.5))
        update_user_gold(CASINO_ACCOUNT, -payout, f"Slot-Auszahlung (Zweifach {symbol})")
        update_user_gold(user_id, payout, f"Kleingewinn bei Slotmachine (Zweifach {symbol})")
        await ctx.send(f"✨ Zwei Symbole gleich ({symbol})! Du bekommst {payout} Gold zurück.")
    else:
        await ctx.send(f"😢 Kein Gewinn. Du verlierst deinen Einsatz von {bet} Gold.")

@bot.command()
@casino_channel_only()
async def blackjack(ctx, bet: int):
    user_id = str(ctx.author.id)
    gold = get_user_gold(user_id)
    casino_gold = get_casino_gold()

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
        await ctx.send("Das Casino hat nicht genug Gold, um deinen Einsatz zu decken. Bitte versuche es später erneut.")
        return

    update_user_gold(user_id, -bet, "Einsatz bei Blackjack", result="Einsatz")

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
                update_user_gold(CASINO_ACCOUNT, bet, "Blackjack Gewinn (Spieler Bust)", result="Gewinn")
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
        update_user_gold(CASINO_ACCOUNT, -payout, "Blackjack Auszahlung", result="Verlust")
        await ctx.send(f"🎉 Du gewinnst! {payout} Gold.")
    elif player_score == dealer_score:
        update_user_gold(user_id, bet, "Rückzahlung bei Unentschieden (Blackjack)", result="Unentschieden")
        await ctx.send("Unentschieden! Dein Einsatz wird zurückerstattet.")
    else:
        update_user_gold(CASINO_ACCOUNT, bet, "Blackjack Gewinn (Spieler verliert)", result="Gewinn")
        update_user_gold(user_id, 0, "Verlust bei Blackjack", result="Verlust")
        await ctx.send(f"Du verlierst {bet} Gold.")

@bot.command()
async def help(ctx):
    help_text = """
**Pingwinsche Staatsbank Bot - Befehle:**

`!balance` - Zeigt deinen Kontostand.
`!addgold <Benutzer/Casino> <Betrag> [Grund]` - (Admin) Fügt Gold hinzu.
`!backupbank` - (Admin) Sendet die bank.json per DM.
`!allbalances` - (Admin) Liste aller Kontostände per DM.
`!goldhistory` - Zeigt deine letzten 10 Gold-Transaktionen und Gesamtbestand.
`!casino_balance` - Zeigt das aktuelle Guthaben des Casinos.
`!slotmachine <Einsatz>` - Spielt an der Slotmaschine (nur im Casino-Channel).
`!blackjack <Einsatz>` - Spielt Blackjack (nur im Casino-Channel).
`!ping` - Prüft die Bot-Antwortzeit.

Casino-Spiele sind nur im Casino-Channel erlaubt.
"""
    await ctx.send(help_text)

@bot.command()
async def ping(ctx):
    await ctx.send(f"Pong! {round(bot.latency * 1000)}ms")

bot.run("DEIN_BOT_TOKEN_HIER")

