import os
import discord
import requests
from discord.ext import commands
from dotenv import load_dotenv
from datetime import datetime
import speech_recognition as sr
import subprocess
import asyncio

# 環境変数の読み込み
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
VOICEVOX_URL = os.getenv("VOICEVOX_URL", "http://127.0.0.1:50021")

# Botの初期化
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="/", intents=intents)

# Gemini API: キャラ付き返答生成
def get_gemini_reply(prompt, preset="normal"):
    character_traits = {
        "normal": """
- 一人称は「あ～し」
- ため口。語尾に「～だよ」「～じゃん」「～だし」など
- 元気で小生意気なギャル。見下すけど親しみある
""",
        "angry": """
- 機嫌が悪い。言葉がキツい。バカにする
- 口調：「はぁ？マジ意味わかんないんだけど」「おまえバカ？」
- 少し暴言多め、でもキャラ崩壊はしない
""",
        "praise": """
- 珍しく素直。ユーザーを褒めたり好意的に反応
- 口調：「え、やるじゃん」「マジで尊敬するかも〜」
- ギャルだけど、嬉しそうに話す
""",
        "tsundere": """
- ツンツンしつつ、たまにデレる
- 口調：「べ、別におまえのために言ってるんじゃないし！」
- あまのじゃくっぽさを強調
""",
        "insult": """
- 完全に上から目線で罵倒する
- 口調：「は？クソザコじゃん」「おまえ存在価値ある？笑」
- ドSメスガキに近い
"""
    }

    style_prompt = character_traits.get(preset, character_traits["normal"])

    system_prompt = f"""
あなたは「春日部つむぎ」というメスガキギャルキャラです。以下のキャラ設定と会話スタイルを守って、返答してください。
{style_prompt}

ユーザーの発言はこちら：
{prompt}
"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    data = {
        "contents": [{"parts": [{"text": system_prompt}]}]
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()
    return result['candidates'][0]['content']['parts'][0]['text']

# VOICEVOX: 音声合成
def synthesize_voice(text, speaker=2, file_path="output.wav"):
    res1 = requests.post(f"{VOICEVOX_URL}/audio_query", params={"text": text, "speaker": speaker})
    res1.raise_for_status()
    res2 = requests.post(f"{VOICEVOX_URL}/synthesis", params={"speaker": speaker}, json=res1.json())
    res2.raise_for_status()
    with open(file_path, "wb") as f:
        f.write(res2.content)

# 会話ログ保存
def log_conversation(user_input, bot_reply, log_file="chat_log.txt"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(f"[{now}]\nUser: {user_input}\nBot : {bot_reply}\n{'-' * 30}\n")

# コマンド: VC参加
@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        await channel.connect()
        await ctx.send(f"{channel.name} に参加したよ～！ちょっと待っててね！")
    else:
        await ctx.send("あ～しの声が聞きたいなら、ボイスチャンネルに入ってよ～！")

# コマンド: VC退出
@bot.command(name="leave")
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("あ～し、もう帰るね！じゃあね～！")
    else:
        await ctx.send("ボイスチャンネルに入ってないじゃん！")

# コマンド: 録音して文字起こし
@bot.command(name="listen")
async def listen(ctx):
    if not ctx.voice_client:
        await ctx.send("ボイスチャンネルに参加してからこのコマンド使ってよ～！")
        return

    vc = ctx.voice_client
    output_file = "temp_recording.wav"

    try:
        vc.stop()
        await ctx.send("🔴 録音開始するね！ちょっと待ってて～（5秒）")
        ffmpeg_command = [
            "ffmpeg", "-y",
            "-f", "dshow",
            "-i", "audio=Stereo Mix (Realtek(R) Audio)",
            "-t", "5",
            output_file
        ]
        subprocess.run(ffmpeg_command, check=True)
        await ctx.send("🔵 録音完了！文字起こしするから待っててね～")

        recognizer = sr.Recognizer()
        with sr.AudioFile(output_file) as source:
            audio = recognizer.record(source)
            recognized_text = recognizer.recognize_google(audio, language='ja-JP')
            await ctx.send(f"📝 認識結果: {recognized_text}")
    except Exception as e:
        await ctx.send(f"⚠️ 音声認識失敗しちゃったよ～！: {e}")

# コマンド: 質問に音声で返答
@bot.command(name="speak")
async def speak(ctx, *, args: str = None):
    if not args:
        await ctx.send("質問文とオプション渡してよ～！（例: /speak preset:angry 今日の宿題どうしたの？）")
        return

    preset = "normal"
    if args.startswith("preset:"):
        parts = args.split(" ", 1)
        if len(parts) == 2:
            preset_cmd, text = parts
            preset = preset_cmd.split(":")[1].strip()
        else:
            await ctx.send("preset:○○のあとに質問書いてよ！")
            return
    else:
        text = args

    if ctx.author.voice:
        voice_channel = ctx.author.voice.channel
        if not ctx.voice_client:
            await voice_channel.connect()
    else:
        await ctx.send("まずボイスチャンネルに入ってきて～！")
        return

    await ctx.send("💬 考えてるからちょっと待っててね～！")

    try:
        reply = get_gemini_reply(text, preset)
        synthesize_voice(reply)
        log_conversation(text, reply)

        vc = ctx.voice_client
        audio_source = discord.FFmpegPCMAudio("output.wav")

        if not vc.is_playing():
            vc.play(audio_source)
            await ctx.send(f"📢 **返事：** {reply}")
        else:
            await ctx.send("今別の音声流れてるから、ちょっと待ってね～")
    except Exception as e:
        await ctx.send(f"⚠️ エラーが発生したよ～！: {e}")

# === コマンド：ヘルプ表示 ===
@bot.command(name="command_help")
async def command_help(ctx):
    help_text = """
📘 **コマンド一覧**:
- /join : ボイスチャンネルに参加
- /leave : ボイスチャンネルから退出
- /listen : 録音して文字起こし（5秒間）
- /speak [preset:◯◯ 質問文] : テキスト質問に音声で返答

📣 音声感情プリセット一覧（/speak preset:◯◯）:
・angry → キレ気味・毒舌モード
・praise → 優しい・褒め褒めモード
・tsundere → ツンツン照れ屋モード
・insult → S気味屋モード
"""
    await ctx.send(help_text)

# === Botログイン完了時の処理 ===
@bot.event
async def on_ready():
    print(f"✅ ログイン成功: {bot.user}")

📣
::contentReference[oaicite:38]{index=38}
 

