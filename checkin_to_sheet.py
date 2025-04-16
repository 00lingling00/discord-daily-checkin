import discord
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
CREDS_JSON = os.environ["GOOGLE_CREDS_JSON"]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def connect_sheet():
    import json
    import tempfile

    # 临时写入凭据文件
    creds_path = tempfile.mktemp()
    with open(creds_path, "w") as f:
        f.write(CREDS_JSON)

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1
    return sheet

def parse_message(msg):
    lines = msg.content.strip().split("\n")
    if not lines:
        return None
    if not lines[0].startswith("出社") and not lines[0].startswith("退社"):
        return None

    data = {
        "日期": msg.created_at.strftime("%Y/%m/%d"),
        "姓名": str(msg.author),
        "打卡类型": "出社" if lines[0].startswith("出社") else "退社",
        "时间": msg.created_at.strftime("%H:%M"),
        "今日计划": "",
        "今日总结": "",
        "工时": "",
    }

    for line in lines:
        if "🧠" in line:
            data["今日计划"] = line.split("：", 1)[-1].strip()
        elif "✅" in line:
            data["今日总结"] = line.split("：", 1)[-1].strip()
        elif "🕘" in line or "🕔" in line:
            m = re.search(r"(\\d{1,2})[:：]?(\\d{2})", line)
            if m:
                data["时间"] = f"{m.group(1).zfill(2)}:{m.group(2)}"
        elif "🕒" in line:
            data["工时"] = line.split("：", 1)[-1].strip()

    return data

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    messages = await channel.history(limit=100).flatten()

    sheet = connect_sheet()
    existing = sheet.get_all_values()

    for msg in messages:
        entry = parse_message(msg)
        if not entry:
            continue
        # 避免重复插入（可选：依据姓名+日期+类型）
        if any(row[:3] == [entry["日期"], entry["姓名"], entry["打卡类型"]] for row in existing):
            continue
        sheet.append_row([
            entry["日期"],
            entry["姓名"],
            entry["打卡类型"],
            entry["时间"],
            entry["今日计划"],
            entry["今日总结"],
            entry["工时"]
        ])
    await client.close()

client.run(DISCORD_TOKEN)
