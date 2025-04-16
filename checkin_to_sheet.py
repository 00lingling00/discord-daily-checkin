# checkin_to_sheet.py

import discord
import re
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import os
import json
import tempfile

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
GOOGLE_SHEET_ID = os.environ["GOOGLE_SHEET_ID"]
GOOGLE_CREDS_JSON = os.environ["GOOGLE_CREDS_JSON"]

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

def connect_sheet():
    creds_path = tempfile.mktemp()
    with open(creds_path, "w") as f:
        f.write(GOOGLE_CREDS_JSON)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    gc = gspread.authorize(creds)
    sheet = gc.open_by_key(GOOGLE_SHEET_ID).sheet1
    return sheet

def parse_message(msg):
    lines = msg.content.strip().split("\n")
    if not lines:
        return None

    msg_type = None
    if lines[0].startswith("出社"):
        msg_type = "出社"
    elif lines[0].startswith("退社"):
        msg_type = "退社"
    else:
        return None

    result = {
        "日期": msg.created_at.strftime("%Y/%m/%d"),
        "姓名": str(msg.author),
        "打卡类型": msg_type,
        "时间": msg.created_at.strftime("%H:%M"),
        "今日计划": "",
        "今日总结": "",
        "工时": ""
    }

    for line in lines:
        if "🧠 今日计划：" in line:
            result["今日计划"] = line.split("：", 1)[-1].strip()
        elif "✅ 今日总结：" in line:
            result["今日总结"] = line.split("：", 1)[-1].strip()
        elif "🕘 时间：" in line or "🕔 时间：" in line:
            match = re.search(r"(\d{1,2})[:：]?(\d{2})", line)
            if match:
                result["时间"] = f"{match.group(1).zfill(2)}:{match.group(2)}"
        elif "🕒 工时：" in line:
            result["工时"] = line.split("：", 1)[-1].strip()

    return result

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")
    channel = client.get_channel(CHANNEL_ID)
    messages = await channel.history(limit=50).flatten()

    sheet = connect_sheet()
    existing = sheet.get_all_values()

    for msg in messages:
        entry = parse_message(msg)
        if not entry:
            continue

        key = [entry["日期"], entry["姓名"], entry["打卡类型"]]
        if any(row[:3] == key for row in existing):
            continue

        # 自动补工时，跨天也支持
        if entry["打卡类型"] == "退社" and not entry["工时"]:
            try:
                out_time = datetime.strptime(entry["日期"] + " " + entry["时间"], "%Y/%m/%d %H:%M")
                for row in reversed(existing):
                    if row[1] == entry["姓名"] and row[2] == "出社":
                        try:
                            in_time = datetime.strptime(row[0] + " " + row[3], "%Y/%m/%d %H:%M")
                            duration = out_time - in_time - timedelta(hours=1)
                            hours = max(duration.total_seconds() / 3600, 0)
                            entry["工时"] = str(round(hours, 1))
                            break
                        except Exception as e:
                            print(f"跨天工时计算失败: {e}")
            except Exception as e:
                print(f"退社时间解析失败: {e}")

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
