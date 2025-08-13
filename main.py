import discord
import asyncio
import time
import os

# === Settings ===
TOKEN = os.getenv("DISCORD_TOKEN")  # Токен бота
SCAN_GUILD_ID = 868387098812629032  # Сервер, который мониторим (не писать туда!)
LOG_CHANNEL_ID = 1404940225951567962  # Канал на служебном сервере, куда слать логи

# === Discord Client ===
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
client = discord.Client(intents=intents, status=discord.Status.invisible)

# Флаг, чтобы не делать повторный снимок при переподключении
initial_scan_done = False

async def log_action(user_id, nickname, action, channel_name, channel_id):
    """Отправляет лог в служебный лог-канал"""
    timestamp = int(time.time())
    log_entry = (
        f"return {{\n"
        f"    user_id: {user_id},\n"
        f"    nickname: '{nickname}',\n"
        f"    action: '{action}',\n"
        f"    timestamp: {timestamp},\n"
        f"    channel_name: '{channel_name}',\n"
        f"    channel_id: {channel_id},\n"
        f"}}"
    )

    log_channel = client.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        try:
            await log_channel.send(f"```{log_entry}```")
        except Exception as e:
            print(f"[ERROR] Failed to send log message: {e}")
        await asyncio.sleep(1)  # Защита от спама

@client.event
async def on_ready():
    global initial_scan_done
    print(f"[INFO] Bot is running as {client.user}")

    # Делаем снимок только при самом первом запуске
    if not initial_scan_done:
        scan_guild = client.get_guild(SCAN_GUILD_ID)
        if not scan_guild:
            print(f"[ERROR] Guild with ID {SCAN_GUILD_ID} not found for scanning")
            return

        print(f"[INFO] Scanning voice channels of guild {scan_guild.name}...")
        for channel in scan_guild.voice_channels:
            for member in channel.members:
                await log_action(member.id, member.display_name, "voice_join", channel.name, channel.id)
                if member.voice and member.voice.self_stream:
                    await log_action(member.id, member.display_name, "stream_start", channel.name, channel.id)
        print("[INFO] Initial scan completed.")
        initial_scan_done = True
    else:
        print("[INFO] Reconnected — skipping initial scan.")

@client.event
async def on_voice_state_update(member, before, after):
    # Перемещение между каналами
    if before.channel != after.channel:
        if before.channel is None and after.channel is not None:
            await log_action(member.id, member.display_name, "voice_join", after.channel.name, after.channel.id)
        elif before.channel is not None and after.channel is None:
            await log_action(member.id, member.display_name, "stream_stop", before.channel.name, before.channel.id)
            await log_action(member.id, member.display_name, "voice_leave", before.channel.name, before.channel.id)
        else:
            await log_action(member.id, member.display_name, "voice_leave", before.channel.name, before.channel.id)
            await log_action(member.id, member.display_name, "voice_join", after.channel.name, after.channel.id)

    # Мьют/анмьют микрофона
    if before.self_mute != after.self_mute:
        action = "mic_mute" if after.self_mute else "mic_unmute"
        ch = after.channel or before.channel
        if ch:
            await log_action(member.id, member.display_name, action, ch.name, ch.id)

    # Мьют/анмьют наушников
    if before.self_deaf != after.self_deaf:
        action = "headphones_mute" if after.self_deaf else "headphones_unmute"
        ch = after.channel or before.channel
        if ch:
            await log_action(member.id, member.display_name, action, ch.name, ch.id)

    # Начало/остановка стрима
    if before.self_stream != after.self_stream:
        action = "stream_start" if after.self_stream else "stream_stop"
        ch = after.channel or before.channel
        if ch:
            await log_action(member.id, member.display_name, action, ch.name, ch.id)

if __name__ == "__main__":
    while True:  # Перезапуск при полном краше
        try:
            client.run(TOKEN, reconnect=True)  # Переподключение при обрыве
        except Exception as e:
            print(f"[ERROR] Bot crashed: {e}")
            time.sleep(5)  # Подождём перед повтором
