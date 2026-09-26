import os
import sys
import types

# ========================================================
# 🚨 [최신 파이썬 버전 에러 대응 패치] Python 3.13+ audioop 결손 문제 해결
# ========================================================
if 'audioop' not in sys.modules:
    dummy_audioop = types.ModuleType('audioop')
    dummy_audioop.error = Exception
    sys.modules['audioop'] = dummy_audioop

import discord
from discord.ext import commands
from aiohttp import web
import datetime
import re
import asyncio

# ========================================================
# 1. 🤖 봇 기본 설정 및 인텐트 권한 활성화
# ========================================================
intents = discord.Intents.default()
intents.message_content = True  
intents.members = True          

bot = commands.Bot(command_prefix="!", intents=intents)

# ⚠️ 설정: 로그 전송 전용 채널 ID 및 금지어 목록
PUNISH_LOG_CHANNEL_ID = 1546457831631224843  
BAD_WORDS = ["느금", "느금마", "금마", "니엄마", "너엄마", "너아빠", "너애비", "니애미", "ㄴㄱㅁ", "ㄴㅇㅁ", "니앰", "앰창", "your mom", "니애비", "느개비", "느금빠", "ㄴㄱㅃ", "금빠", "창년", "섹스", "색스", "색's", "섹's", "섹s", "색s", "운지", "응디", "운지", "응지", "보지", "자지", "좆물", "봊물", "보지물", "자지물", "정액"]

# ========================================================
# 2. 🌐 충돌 없는 비동기 웹 서버 (Uptime용)
# ========================================================
async def handle(request):
    return web.Response(text="Bot is alive and perfectly running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    
    port = int(os.environ.get("PORT", 10000))
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f" Web Server is successfully running on port {port}")

# ========================================================
# 3. 🚨 디스코드 시스템 이벤트 및 제재 함수
# ========================================================
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
    print("------ 자동 검열 + 수동 제재 + 제재 해제 통합 로그 시스템 가동 중 ------")

async def punish_member(guild, member, channel, reason_text, original_content=None):
    if member.guild_permissions.administrator:
        return

    log_channel = bot.get_channel(PUNISH_LOG_CHANNEL_ID) or channel
    current_crime_level = 0
    current_role = None

    for role in member.roles:
        match = re.match(r"전과\s*(\d+)범", role.name)
        if match:
            current_crime_level = int(match.group(1))
            current_role = role
            break

    next_crime_level = current_crime_level + 1
    is_ban = next_crime_level >= 20
    next_role_name = f"전과 {next_crime_level}범"
    next_role = discord.utils.get(guild.roles, name=next_role_name)

    if not is_ban:
        if next_role:
            try:
                if current_role:
                    await member.remove_roles(current_role)
                await member.add_roles(next_role)
            except discord.Forbidden:
                await log_channel.send("❌ 봇의 역할 순위가 낮아 전과 역할을 부여하지 못했습니다.")
                return
        else:
            await log_channel.send(f"❌ 서버에 `{next_role_name}` 역할이 존재하지 않습니다. 역할 생성을 확인해주세요.")
            return

    embed = discord.Embed(title="🚨 사용자 경고 및 제재 안내", color=0xff0000)
    embed.add_field(name="제재 대상", value=member.mention, inline=True)
    embed.add_field(name="현재 상태", value=f"**{next_role_name}** 승급" if not is_ban else "**영구 차단**", inline=True)
    
    if original_content:
        embed.add_field(name="적발된 메시지 내용", value=f"||{original_content}||", inline=False)
    else:
        embed.add_field(name="적발된 메시지 내용", value="관리자가 수동 제재를 적용함", inline=False)

    if is_ban:
        embed.add_field(name="처벌 내용", value="**서버 영구 차단 (Ban)**", inline=False)
        embed.set_footer(text="전과 20범 누적으로 인해 서버에서 영구 격리 조치되었습니다.")
    else:
        timeout_days = next_crime_level
        timeout_hours = timeout_days * 24
        duration = datetime.timedelta(days=timeout_days)
        embed.add_field(name="타임아웃 처벌", value=f"**{timeout_days}일 ({timeout_hours}시간)** 동안 말하기 금지", inline=False)
        embed.set_footer(text="경고가 누적될 때마다 처벌 시간이 24시간(1일)씩 늘어납니다.")

    try:
        if is_ban:
            await member.ban(reason=f"{reason_text} (누적 {next_crime_level}회 - 20범 이상 영구 제한)")
        else:
            await member.timeout(duration, reason=f"{reason_text} (누적 {next_crime_level}회)")
        await log_channel.send(embed=embed)
    except discord.Forbidden:
        await log_channel.send("❌ 봇에게 멤버 제재(타임아웃/추방) 권한이 부족합니다.")

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

    clean_content = message.content.replace(" ", "")
    if any(bad_word in clean_content for bad_word in BAD_WORDS):
        captured_content = message.content
        try:
            await message.delete()
        except discord.Forbidden:
            pass
        await punish_member(message.guild, message.author, message.channel, "금지어 사용 적발", original_content=captured_content)
        return

    user_msg = message.content.strip()
    if user_msg in ["안녕하세요", "안녕"]:
        await message.channel.send(f"반가워요, {message.author.mention}님! 오늘도 좋은 하루 되세요! 😊")

    await bot.process_commands(message)

# ========================================================
# 4. 🛠️ 관리자 명령어 (!제재 / !제재지우기)
# ========================================================
@bot.command(name="제재")
@commands.has_permissions(moderate_members=True)
async def manual_punish(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass
    await punish_member(ctx.guild, member, ctx.channel, "관리자에 의한 수동 제재")

@bot.command(name="제재지우기")
@commands.has_permissions(moderate_members=True)
async def remove_punish(ctx, member: discord.Member):
    try:
        await ctx.message.delete()
    except discord.Forbidden:
        pass

    log_channel = bot.get_channel(PUNISH_LOG_CHANNEL_ID) or ctx.channel
    current_crime_level = 0
    current_role = None

    for role in member.roles:
        match = re.match(r"전과\s*(\d+)범", role.name)
        if match:
            current_crime_level = int(match.group(1))
            current_role = role
            break

    if current_crime_level == 0:
        try:
            await member.timeout(None, reason="관리자에 의한 제재 해제")
        except discord.Forbidden:
            pass
        embed = discord.Embed(title=f"🔓 {member.display_name} 님의 제재가 지워졌습니다", color=0x00ff00)
        embed.add_field(name="제재 해제 대상", value=member.mention, inline=True)
        embed.add_field(name="명령어 실행자", value=ctx.author.mention, inline=True)
        embed.add_field(name="처리 내용", value="**타임아웃 즉시 해제 (기존 전과 역할 없음)**", inline=False)
        await log_channel.send(embed=embed)
        return

    prev_crime_level = current_crime_level - 1
    prev_role_name = f"전과 {prev_crime_level}범" if prev_crime_level > 0 else None

    try:
        if current_role:
            await member.remove_roles(current_role)
        if prev_role_name:
            prev_role = discord.utils.get(ctx.guild.roles, name=prev_role_name)
            if prev_role:
                await member.add_roles(prev_role)
    except discord.Forbidden:
        await log_channel.send("❌ 봇의 역할 순위가 낮아 전과 역할을 변경하지 못했습니다.")
        return

    try:
        await member.timeout(None, reason="관리자에 의한 제재 감면")
    except discord.Forbidden:
        pass

    embed = discord.Embed(title=f"🔓 {member.display_name} 님의 제재가 지워졌습니다", color=0x00ff00)
    embed.add_field(name="제재 해제 대상", value=member.mention, inline=True)
    embed.add_field(name="명령어 실행자", value=ctx.author.mention, inline=True)
    embed.add_field(name="처리 내용", value="**타임아웃 즉시 해제 및 전과 1회 차감**", inline=False)
    embed.add_field(name="변경 전과 상태", value=f"전과 {current_crime_level}범 ➔ **" + (f"전과 {prev_crime_level}범" if prev_crime_level > 0 else "민간인 (전과 없음)") + "**", inline=False)
    embed.set_footer(text="지정된 관리자 권한에 의해 처벌이 감면되었습니다.")
    await log_channel.send(embed=embed)

# ========================================================
# 5. 🚀 비동기 동시 제어 파트 (시동 엔진)
# ========================================================
async def main():
    await start_web_server()
    async with bot:
        await bot.start(os.environ['BOT_TOKEN'])

if __name__ == "__main__":
    asyncio.run(main())