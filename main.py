```python
# main.py
import asyncio
import json
import os
import random
import string
import requests
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "0").split(",") if x.strip()]
DATA_FILE = "/app/data.json"

if not BOT_TOKEN:
    print("❌ Установи BOT_TOKEN!")
    exit(1)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

PERM_SEND = 0x800
PERM_VIEW = 0x400

def is_admin(user_id):
    return user_id in ADMIN_IDS

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except:
            pass
    return {}

def save_data():
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(users, f, ensure_ascii=False)
    except Exception as e:
        print(f"Save error: {e}")

users = load_data()

REST_S = {}
DM_S = {}

def get_ua(mobile=False):
    if mobile:
        return random.choice([
            "Mozilla/5.0 (Linux; Android 13) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2) Mobile/15E148",
        ])
    return random.choice([
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    ])

def get_props(mobile=False):
    import base64
    p = {
        "os": "Android" if mobile else "Windows",
        "os_version": "13" if mobile else "10.0.22631",
        "browser": "Chrome Mobile" if mobile else "Chrome",
        "browser_version": "120.0.6099.230" if mobile else "120.0.6099.130",
        "device": "SM-S918B" if mobile else "",
        "system_locale": "en-US" if mobile else "ru-RU",
        "browser_user_agent": get_ua(mobile),
        "browser_build_id": str(random.randint(500000, 999999)),
        "release_channel": "stable",
        "client_build_number": random.randint(180000, 190000) if mobile else random.randint(250000, 260000),
        "client_event_source": None
    }
    return base64.b64encode(json.dumps(p).encode()).decode()

def get_rest_session(token):
    s = requests.Session()
    s.headers.update({
        "Accept": "*/*", "Accept-Language": "ru-RU,ru;q=0.9",
        "Origin": "https://discord.com", "Referer": "https://discord.com/channels/@me",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120"',
        "Sec-Ch-Ua-Mobile": "?0", "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
    })
    return s

def get_dm_session(token):
    s = requests.Session()
    s.headers.update({
        "Accept": "application/json", "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://discord.com", "Referer": "https://discord.com/channels/@me",
        "Sec-Ch-Ua": '"Chromium";v="121"', "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
    })
    return s

def rest_req(token, method, url, **kw):
    if token not in REST_S:
        REST_S[token] = get_rest_session(token)
    h = {"Authorization": token, "User-Agent": get_ua(), "X-Super-Properties": get_props(), "X-Discord-Locale": "ru"}
    if method == "GET":
        return REST_S[token].get(url, headers=h, timeout=15, **kw)
    return REST_S[token].post(url, headers={**h, "Content-Type": "application/json"}, timeout=15, **kw)

def dm_req(token, method, url, **kw):
    if token not in DM_S:
        DM_S[token] = get_dm_session(token)
    h = {"Authorization": token, "User-Agent": get_ua(True), "X-Super-Properties": get_props(True), "X-Discord-Locale": "en-US", "X-Fingerprint": ''.join(random.choices(string.ascii_lowercase + string.digits, k=32))}
    if method == "GET":
        return DM_S[token].get(url, headers=h, timeout=15, **kw)
    return DM_S[token].post(url, headers={**h, "Content-Type": "application/json"}, timeout=15, **kw)

def get_guilds(token):
    guilds, after = [], None
    while True:
        r = rest_req(token, "GET", "https://discord.com/api/v9/users/@me/guilds", params={"limit": 100, "after": after} if after else {"limit": 100})
        if not r or r.status_code != 200 or not r.json(): break
        guilds.extend(r.json())
        after = r.json()[-1]["id"]
        if len(r.json()) < 100: break
    return guilds

def get_friends(token):
    r = rest_req(token, "GET", "https://discord.com/api/v9/users/@me/relationships")
    return [x['user'] for x in r.json() if r and r.status_code == 200 and x.get('type') == 1] if r else []

def get_dms(token):
    r = rest_req(token, "GET", "https://discord.com/api/v9/users/@me/channels")
    if not r or r.status_code != 200: return []
    result = []
    for ch in r.json():
        if ch.get('type') == 3:
            name = ch.get('name') or ', '.join(x.get('username','?') for x in ch.get('recipients',[])[:3])
            if len(ch.get('recipients',[])) > 3: name += f" +{len(ch['recipients'])-3}"
            result.append({"id": ch["id"], "name": name})
    return result

def get_guild_channels(token, gid):
    r = rest_req(token, "GET", f"https://discord.com/api/v9/guilds/{gid}/channels")
    if not r or r.status_code != 200: 
        return []
    result = []
    for c in r.json():
        if c.get('type') != 0:
            continue
        perms = c.get('permissions', 0)
        if perms == 0 or ((perms & PERM_VIEW) and (perms & PERM_SEND)):
            result.append({"id": c["id"], "name": c["name"]})
    return result

def create_dm(token, uid):
    r = rest_req(token, "POST", "https://discord.com/api/v9/users/@me/channels", json={"recipient_id": uid})
    return r.json().get('id') if r and r.status_code == 200 else None

def send_rest(token, ch_id, msg):
    return rest_req(token, "POST", f"https://discord.com/api/v9/channels/{ch_id}/messages", json={"content": msg, "nonce": ''.join(random.choices(string.digits, k=18)), "tts": False})

def send_dm(token, ch_id, msg):
    return dm_req(token, "POST", f"https://discord.com/api/v10/channels/{ch_id}/messages", json={"content": msg, "nonce": ''.join(random.choices(string.ascii_lowercase + string.digits, k=20)), "tts": False})

def ensure_user(uid):
    if uid not in users:
        users[uid] = {"accounts": [], "targets": {}, "settings": {"msg_delay": 7, "jitter": 2, "dm_delay": 15, "round_delay": 45, "typing": True}, "spamming": False, "stop": False, "msgs": [], "sent": 0}

class States(StatesGroup):
    waiting_token = State()
    waiting_msg = State()
    waiting_admin_id = State()

def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Добавить токен", callback_data="add_token")],
        [InlineKeyboardButton(text="📋 Мои аккаунты", callback_data="list_accs")],
        [InlineKeyboardButton(text="🎯 Собрать цели", callback_data="collect")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="📝 Сообщение", callback_data="set_msg")],
        [InlineKeyboardButton(text="🚀 Старт спама", callback_data="start_spam")],
        [InlineKeyboardButton(text="🛑 Стоп", callback_data="stop_spam")],
    ])

def admin_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔑 Добавить токен", callback_data="add_token")],
        [InlineKeyboardButton(text="📋 Мои аккаунты", callback_data="list_accs")],
        [InlineKeyboardButton(text="🎯 Собрать цели", callback_data="collect")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="settings")],
        [InlineKeyboardButton(text="📝 Сообщение", callback_data="set_msg")],
        [InlineKeyboardButton(text="🚀 Старт спама", callback_data="start_spam")],
        [InlineKeyboardButton(text="🛑 Стоп", callback_data="stop_spam")],
        [InlineKeyboardButton(text="━━━ АДМИНКА ━━━", callback_data="admin_none")],
        [InlineKeyboardButton(text="👤 Список юзеров", callback_data="admin_users")],
        [InlineKeyboardButton(text="➕ Добавить админа", callback_data="admin_add")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_del")],
        [InlineKeyboardButton(text="🗑 Очистить юзера", callback_data="admin_wipe")],
        [InlineKeyboardButton(text="📡 Статистика", callback_data="admin_stats")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="← Назад", callback_data="back")]
    ])

def collect_kb(uid):
    ensure_user(uid)
    t = users[uid].get("targets", {})
    btns = []
    for uname, data in t.items():
        g_c = sum(1 for g in data.get("guilds", []) if g.get("selected"))
        f_c = sum(1 for f in data.get("friends", []) if f.get("selected"))
        d_c = sum(1 for d in data.get("dms", []) if d.get("selected"))
        btns.append([InlineKeyboardButton(text=f"🖥 {uname}: {g_c}/{len(data.get('guilds',[]))} серв.", callback_data=f"tgl_g_{uname}")])
        btns.append([InlineKeyboardButton(text=f"👥 {uname}: {f_c}/{len(data.get('friends',[]))} друз.", callback_data=f"tgl_f_{uname}")])
        btns.append([InlineKeyboardButton(text=f"💬 {uname}: {d_c}/{len(data.get('dms',[]))} групп", callback_data=f"tgl_d_{uname}")])
    btns.append([InlineKeyboardButton(text="✅ Загрузить каналы", callback_data="load_channels")])
    btns.append([InlineKeyboardButton(text="← Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=btns)

def settings_kb(s):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="REST -", callback_data="rd-"), InlineKeyboardButton(text="REST +", callback_data="rd+")],
        [InlineKeyboardButton(text="Разброс -", callback_data="j-"), InlineKeyboardButton(text="Разброс +", callback_data="j+")],
        [InlineKeyboardButton(text="DM -", callback_data="dd-"), InlineKeyboardButton(text="DM +", callback_data="dd+")],
        [InlineKeyboardButton(text="Пауза -", callback_data="pd-"), InlineKeyboardButton(text="Пауза +", callback_data="pd+")],
        [InlineKeyboardButton(text=f"⌨️ {'ВЫКЛ' if s['typing'] else 'ВКЛ'}", callback_data="tt")],
        [InlineKeyboardButton(text="← Назад", callback_data="back")],
    ])

@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    uid = m.from_user.id
    ensure_user(uid)
    save_data()
    if is_admin(uid):
        await m.answer("👑 <b>Админ-панель</b>\n\nПривет, босс!", reply_markup=admin_main_kb())
    else:
        await m.answer("👋 Доступ закрыт.", reply_markup=main_kb())

@router.callback_query(F.data == "back")
async def cb_back(c: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = c.from_user.id
    if is_admin(uid):
        try: await c.message.edit_text("👑 <b>Админ-панель</b>", reply_markup=admin_main_kb())
        except: pass
    else:
        try: await c.message.edit_text("🏠 Главное меню", reply_markup=main_kb())
        except: pass

@router.callback_query(F.data == "admin_none")
async def cb_admin_none(c: CallbackQuery):
    await c.answer()

@router.callback_query(F.data == "add_token")
async def cb_add_token(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    await state.set_state(States.waiting_token)
    try: await c.message.edit_text("🔑 Отправь Discord токен:", reply_markup=back_kb())
    except: pass

@router.message(States.waiting_token)
async def got_token(m: Message, state: FSMContext):
    token = m.text.strip()
    if not token:
        await m.answer("❌ Пусто!")
        return
    r = rest_req(token, "GET", "https://discord.com/api/v9/users/@me")
    if not r or r.status_code != 200:
        await m.answer("❌ Неверный токен!")
        return
    uname = r.json().get('username', '?')
    uid = m.from_user.id
    ensure_user(uid)
    users[uid]["accounts"].append({"token": token, "username": uname})
    save_data()
    await state.clear()
    kb = admin_main_kb() if is_admin(uid) else main_kb()
    await m.answer(f"✅ Добавлен: <code>{uname}</code>\nВсего: {len(users[uid]['accounts'])}", reply_markup=kb)

@router.callback_query(F.data == "list_accs")
async def cb_list(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    uid = c.from_user.id
    ensure_user(uid)
    accs = users[uid]["accounts"]
    if not accs:
        try: await c.message.edit_text("❌ Нет аккаунтов", reply_markup=back_kb())
        except: pass
        return
    text = f"📋 Аккаунтов: {len(accs)}\n\n"
    for i, a in enumerate(accs):
        text += f"{i+1}. <code>{a['username']}</code>\n"
    text += "\n/del — удалить все"
    try: await c.message.edit_text(text, reply_markup=back_kb())
    except: pass

@router.message(Command("del"))
async def cmd_del(m: Message):
    uid = m.from_user.id
    if not is_admin(uid):
        await m.answer("🚫")
        return
    ensure_user(uid)
    users[uid]["accounts"] = []
    users[uid]["targets"] = {}
    save_data()
    await m.answer("🗑 Удалено", reply_markup=admin_main_kb())

@router.callback_query(F.data == "collect")
async def cb_collect(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    uid = c.from_user.id
    ensure_user(uid)
    if not users[uid]["accounts"]:
        await c.answer("❌ Добавь токены!", show_alert=True)
        return
    try: await c.message.edit_text("⏳ Собираю...", reply_markup=back_kb())
    except: pass
    asyncio.create_task(do_collect(uid, c.message.chat.id))

async def do_collect(uid, chat_id):
    ensure_user(uid)
    accs = users[uid]["accounts"]
    targets = {}
    for acc in accs:
        token, uname = acc["token"], acc["username"]
        await bot.send_message(chat_id, f"📡 <code>{uname}</code>: сбор...")
        try:
            loop = asyncio.get_event_loop()
            guilds, friends, dms = await asyncio.gather(
                loop.run_in_executor(None, get_guilds, token),
                loop.run_in_executor(None, get_friends, token),
                loop.run_in_executor(None, get_dms, token)
            )
        except:
            guilds, friends, dms = [], [], []
        targets[uname] = {
            "token": token,
            "guilds": [{"id": g["id"], "name": g.get('name','?'), "selected": True} for g in guilds],
            "friends": [{"id": f["id"], "name": f"@{f.get('username','?')}", "selected": False} for f in friends],
            "dms": [{"id": d["id"], "name": d["name"], "selected": True} for d in dms],
        }
        await bot.send_message(chat_id, f"✅ <code>{uname}</code>:\n🖥 {len(guilds)} | 👥 {len(friends)} | 💬 {len(dms)}")
    users[uid]["targets"] = targets
    save_data()
    await bot.send_message(chat_id, "✅ Выбери что спамить:", reply_markup=collect_kb(uid))

@router.callback_query(F.data.startswith("tgl_g_"))
async def cb_tgl_g(c: CallbackQuery):
    uid = c.from_user.id
    ensure_user(uid)
    uname = c.data.split("_", 2)[2]
    t = users[uid]["targets"][uname]
    sel = all(g["selected"] for g in t["guilds"])
    for g in t["guilds"]: g["selected"] = not sel
    save_data()
    await c.answer("Готово")
    try: await c.message.edit_reply_markup(reply_markup=collect_kb(uid))
    except: pass

@router.callback_query(F.data.startswith("tgl_f_"))
async def cb_tgl_f(c: CallbackQuery):
    uid = c.from_user.id
    ensure_user(uid)
    uname = c.data.split("_", 2)[2]
    t = users[uid]["targets"][uname]
    sel = all(f["selected"] for f in t["friends"])
    for f in t["friends"]: f["selected"] = not sel
    save_data()
    await c.answer("Готово")
    try: await c.message.edit_reply_markup(reply_markup=collect_kb(uid))
    except: pass

@router.callback_query(F.data.startswith("tgl_d_"))
async def cb_tgl_d(c: CallbackQuery):
    uid = c.from_user.id
    ensure_user(uid)
    uname = c.data.split("_", 2)[2]
    t = users[uid]["targets"][uname]
    sel = all(d["selected"] for d in t["dms"])
    for d in t["dms"]: d["selected"] = not sel
    save_data()
    await c.answer("Готово")
    try: await c.message.edit_reply_markup(reply_markup=collect_kb(uid))
    except: pass

@router.callback_query(F.data == "load_channels")
async def cb_load_channels(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    try: await c.message.edit_text("⏳ Параллельная проверка доступа...")
    except: pass
    asyncio.create_task(do_load_channels(c.from_user.id, c.message.chat.id))

async def do_load_channels(uid, chat_id):
    ensure_user(uid)
    targets = users[uid].get("targets", {})
    total_rest, total_dm = 0, 0
    
    for uname, data in targets.items():
        token = data["token"]
        rest_ch, dm_ch = [], []
        check_list = []
        
        # Собираем серверные каналы
        for g in data.get("guilds", []):
            if not g.get("selected"): continue
            try:
                loop = asyncio.get_event_loop()
                chs = await loop.run_in_executor(None, get_guild_channels, token, g["id"])
                for ch in chs:
                    check_list.append({"id": ch["id"], "name": ch["name"]})
            except:
                pass
        
        # Собираем групповые чаты
        for d in data.get("dms", []):
            if not d.get("selected"): continue
            check_list.append({"id": d["id"], "name": d["name"]})
        
        # Безопасная параллельная проверка REST каналов
        if check_list:
            async def safe_check(ch_item):
                try:
                    loop = asyncio.get_event_loop()
                    ch_id = ch_item["id"]
                    tk = token
                    def req_check():
                        r = rest_req(tk, "GET", f"https://discord.com/api/v9/channels/{ch_id}/messages?limit=1")
                        return r and r.status_code == 200
                    ok = await loop.run_in_executor(None, req_check)
                    return ok
                except:
                    return False
            
            loop = asyncio.get_event_loop()
            tasks = [safe_check(ch) for ch in check_list]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for ch_item, res in zip(check_list, results):
                if res is True:
                    rest_ch.append({"id": ch_item["id"], "name": ch_item["name"], "api": "rest"})
        
        # Безопасное параллельное создание DM
        friends_list = [f for f in data.get("friends", []) if f.get("selected")]
        if friends_list:
            async def safe_dm(friend):
                try:
                    loop = asyncio.get_event_loop()
                    f_id = friend["id"]
                    tk = token
                    def req_dm():
                        return create_dm(tk, f_id)
                    dm_id = await loop.run_in_executor(None, req_dm)
                    return dm_id
                except:
                    return None
            
            dm_tasks = [safe_dm(f) for f in friends_list]
            dm_results = await asyncio.gather(*dm_tasks, return_exceptions=True)
            
            for friend, dm_id in zip(friends_list, dm_results):
                if dm_id and isinstance(dm_id, str):
                    dm_ch.append({"id": dm_id, "name": friend["name"], "api": "dm"})
        
        data["rest_channels"] = rest_ch
        data["dm_channels"] = dm_ch
        total_rest += len(rest_ch)
        total_dm += len(dm_ch)
        await bot.send_message(chat_id, f"✅ <code>{uname}</code>:\n🖥 REST: {len(rest_ch)}\n📱 DM: {len(dm_ch)}")
    
    users[uid]["targets"] = targets
    save_data()
    await bot.send_message(chat_id, f"🎉 Готово!\n🖥 REST: {total_rest}\n📱 DM: {total_dm}", reply_markup=admin_main_kb())

@router.callback_query(F.data == "settings")
async def cb_settings(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    uid = c.from_user.id
    ensure_user(uid)
    s = users[uid]["settings"]
    text = f"""⚙️ <b>Настройки</b>

🖥 REST: <code>{s['msg_delay']}</code>с ±<code>{s['jitter']}</code>с
📱 DM: <code>{s['dm_delay']}</code>с
😴 Пауза: <code>{s['round_delay']}</code>с
⌨️ Набор: {'✅' if s['typing'] else '❌'}"""
    try: await c.message.edit_text(text, reply_markup=settings_kb(s))
    except: pass

@router.callback_query(F.data == "rd-")
async def cb_rd_m(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["msg_delay"] = max(1, users[c.from_user.id]["settings"]["msg_delay"] - 1); save_data(); await cb_settings(c)

@router.callback_query(F.data == "rd+")
async def cb_rd_p(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["msg_delay"] = min(60, users[c.from_user.id]["settings"]["msg_delay"] + 1); save_data(); await cb_settings(c)

@router.callback_query(F.data == "j-")
async def cb_j_m(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["jitter"] = max(0, users[c.from_user.id]["settings"]["jitter"] - 0.5); save_data(); await cb_settings(c)

@router.callback_query(F.data == "j+")
async def cb_j_p(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["jitter"] = min(10, users[c.from_user.id]["settings"]["jitter"] + 0.5); save_data(); await cb_settings(c)

@router.callback_query(F.data == "dd-")
async def cb_dd_m(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["dm_delay"] = max(3, users[c.from_user.id]["settings"]["dm_delay"] - 1); save_data(); await cb_settings(c)

@router.callback_query(F.data == "dd+")
async def cb_dd_p(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["dm_delay"] = min(120, users[c.from_user.id]["settings"]["dm_delay"] + 1); save_data(); await cb_settings(c)

@router.callback_query(F.data == "pd-")
async def cb_pd_m(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["round_delay"] = max(5, users[c.from_user.id]["settings"]["round_delay"] - 5); save_data(); await cb_settings(c)

@router.callback_query(F.data == "pd+")
async def cb_pd_p(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["round_delay"] = min(300, users[c.from_user.id]["settings"]["round_delay"] + 5); save_data(); await cb_settings(c)

@router.callback_query(F.data == "tt")
async def cb_tt(c: CallbackQuery):
    ensure_user(c.from_user.id); users[c.from_user.id]["settings"]["typing"] = not users[c.from_user.id]["settings"]["typing"]; save_data(); await cb_settings(c)

@router.callback_query(F.data == "set_msg")
async def cb_set_msg(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    await state.set_state(States.waiting_msg)
    try: await c.message.edit_text("📝 Отправь сообщение:", reply_markup=back_kb())
    except: pass

@router.message(States.waiting_msg)
async def got_msg(m: Message, state: FSMContext):
    uid = m.from_user.id
    ensure_user(uid)
    users[uid]["msgs"] = [m.text.strip()]
    save_data()
    await state.clear()
    await m.answer(f"✅ Сообщение: <code>{m.text[:50]}</code>", reply_markup=admin_main_kb())

@router.callback_query(F.data == "start_spam")
async def cb_start(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    uid = c.from_user.id
    ensure_user(uid)
    u = users[uid]
    if not u["accounts"]:
        await c.answer("❌ Нет аккаунтов!", show_alert=True)
        return
    if not u.get("targets"):
        await c.answer("❌ Собери цели!", show_alert=True)
        return
    rest_total = 0
    dm_total = 0
    for uname, data in u["targets"].items():
        rest_total += len(data.get("rest_channels", []))
        dm_total += len(data.get("dm_channels", []))
    if rest_total == 0 and dm_total == 0:
        await c.answer(f"❌ Нет каналов! REST:{rest_total} DM:{dm_total}\nСобери и загрузи каналы!", show_alert=True)
        return
    if not u["msgs"]:
        await c.answer("❌ Установи сообщение!", show_alert=True)
        return
    if u["spamming"]:
        await c.answer("⚠️ Уже спамим!", show_alert=True)
        return
    u["spamming"] = True
    u["sent"] = 0
    u["stop"] = False
    save_data()
    try:
        await c.message.edit_text(f"🚀 <b>СПАМ ЗАПУЩЕН</b>\n\n🖥 Серверы+группы: {rest_total}\n📱 ЛС: {dm_total}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛑 СТОП", callback_data="stop_spam")]
        ]))
    except: pass
    asyncio.create_task(do_spam(uid, c.message.chat.id))

async def do_spam(uid, chat_id):
    ensure_user(uid)
    u = users[uid]
    s = u["settings"]
    msg = u["msgs"][0]
    sent, rnd = 0, 0
    while not u.get("stop", False):
        rnd += 1
        rest_sent, dm_sent = 0, 0
        
        for uname, data in u["targets"].items():
            if u.get("stop"): break
            channels = data.get("rest_channels", [])
            if not channels: continue
            random.shuffle(channels)
            for ch in channels[:]:
                if u.get("stop"): break
                try:
                    loop = asyncio.get_event_loop()
                    m = msg + " " if random.random() < 0.15 else msg
                    r = await loop.run_in_executor(None, send_rest, data["token"], ch["id"], m)
                    if r and r.status_code == 200:
                        sent += 1; rest_sent += 1
                    elif r and r.status_code == 403:
                        if ch in data["rest_channels"]:
                            data["rest_channels"].remove(ch)
                            save_data()
                        continue
                    elif r and r.status_code == 429:
                        retry = r.json().get('retry_after', 5)
                        await asyncio.sleep(retry + 1)
                        continue
                except: pass
                delay = max(0.5, s["msg_delay"] + random.uniform(-s["jitter"], s["jitter"]))
                await asyncio.sleep(delay)
        
        if rest_sent > 0:
            try: await bot.send_message(chat_id, f"📊 Р{rnd} REST: +{rest_sent} | Всего: {sent}")
            except: pass
        
        if not u.get("stop"): await asyncio.sleep(random.uniform(5, 15))
        
        for uname, data in u["targets"].items():
            if u.get("stop"): break
            channels = data.get("dm_channels", [])
            if not channels: continue
            random.shuffle(channels)
            for ch in channels[:]:
                if u.get("stop"): break
                try:
                    loop = asyncio.get_event_loop()
                    m = msg + "  " if random.random() < 0.1 else msg
                    r = await loop.run_in_executor(None, send_dm, data["token"], ch["id"], m)
                    if r and r.status_code == 200:
                        sent += 1; dm_sent += 1
                    elif r and r.status_code == 403:
                        if ch in data["dm_channels"]:
                            data["dm_channels"].remove(ch)
                            save_data()
                        continue
                    elif r and r.status_code == 429:
                        retry = r.json().get('retry_after', 10)
                        await asyncio.sleep(retry + 3)
                        continue
                except: pass
                dm_actual = max(3, s["dm_delay"] + random.uniform(-1, 2))
                await asyncio.sleep(dm_actual)
        
        if dm_sent > 0:
            try: await bot.send_message(chat_id, f"📊 Р{rnd} DM: +{dm_sent} | Всего: {sent}")
            except: pass
        
        u["sent"] = sent
        save_data()
        
        if not u.get("stop"):
            try: await bot.send_message(chat_id, f"😴 Раунд {rnd}. Отдых {s['round_delay']}с...")
            except: pass
            await asyncio.sleep(s["round_delay"])
    
    u["spamming"] = False
    save_data()
    try: await bot.send_message(chat_id, f"🛑 Стоп! Отправлено: {sent}", reply_markup=admin_main_kb())
    except: pass

@router.callback_query(F.data == "stop_spam")
async def cb_stop(c: CallbackQuery):
    ensure_user(c.from_user.id)
    users[c.from_user.id]["stop"] = True
    save_data()
    await c.answer("🛑 Останавливаю...", show_alert=True)

@router.callback_query(F.data == "admin_users")
async def cb_admin_users(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    if not users:
        try: await c.message.edit_text("👤 Юзеров нет", reply_markup=back_kb())
        except: pass
        return
    text = "👤 <b>Юзеры:</b>\n\n"
    for u_id, data in users.items():
        adm = "👑" if is_admin(int(u_id)) else "👤"
        acc = len(data.get("accounts", []))
        rest = sum(len(d.get("rest_channels", [])) for d in data.get("targets", {}).values())
        dm = sum(len(d.get("dm_channels", [])) for d in data.get("targets", {}).values())
        st = "🟢 Спамит" if data.get("spamming") else "⚪ Idle"
        text += f"{adm} <code>{u_id}</code> | {acc} акк | REST:{rest} DM:{dm} | {st}\n"
    try: await c.message.edit_text(text, reply_markup=back_kb())
    except: pass

@router.callback_query(F.data == "admin_add")
async def cb_admin_add(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    await state.set_state(States.waiting_admin_id)
    try: await c.message.edit_text("➕ Отправь Telegram ID нового админа:", reply_markup=back_kb())
    except: pass

@router.callback_query(F.data == "admin_del")
async def cb_admin_del(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    await state.set_state(States.waiting_admin_id)
    try: await c.message.edit_text("➖ Отправь Telegram ID для удаления:", reply_markup=back_kb())
    except: pass

@router.callback_query(F.data == "admin_wipe")
async def cb_admin_wipe(c: CallbackQuery, state: FSMContext):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    await state.set_state(States.waiting_admin_id)
    try: await c.message.edit_text("🗑 Отправь Telegram ID юзера для очистки:", reply_markup=back_kb())
    except: pass

@router.message(States.waiting_admin_id)
async def got_admin_id(m: Message, state: FSMContext):
    if not is_admin(m.from_user.id):
        await m.answer("🚫")
        return
    try:
        target_id = int(m.text.strip())
    except:
        await m.answer("❌ Это не число!")
        return
    if target_id in ADMIN_IDS:
        ADMIN_IDS.remove(target_id)
        await m.answer(f"➖ Удалён из админов: <code>{target_id}</code>", reply_markup=admin_main_kb())
    elif str(target_id) in users:
        users[str(target_id)] = {"accounts": [], "targets": {}, "settings": {"msg_delay": 7, "jitter": 2, "dm_delay": 15, "round_delay": 45, "typing": True}, "spamming": False, "stop": False, "msgs": [], "sent": 0}
        save_data()
        await m.answer(f"🗑 Очищен: <code>{target_id}</code>", reply_markup=admin_main_kb())
    else:
        ADMIN_IDS.append(target_id)
        await m.answer(f"➕ Добавлен админ: <code>{target_id}</code>", reply_markup=admin_main_kb())
    await state.clear()

@router.message(Command("addadmin"))
async def cmd_addadmin(m: Message):
    if not is_admin(m.from_user.id):
        await m.answer("🚫")
        return
    try:
        target_id = int(m.text.split()[1])
    except:
        await m.answer("❌ /addadmin <ID>")
        return
    if target_id not in ADMIN_IDS:
        ADMIN_IDS.append(target_id)
    await m.answer(f"➕ Админ: <code>{target_id}</code>\nСписок: {ADMIN_IDS}")

@router.message(Command("deladmin"))
async def cmd_deladmin(m: Message):
    if not is_admin(m.from_user.id):
        await m.answer("🚫")
        return
    try:
        target_id = int(m.text.split()[1])
    except:
        await m.answer("❌ /deladmin <ID>")
        return
    if target_id in ADMIN_IDS:
        ADMIN_IDS.remove(target_id)
    await m.answer(f"➖ Удалён: <code>{target_id}</code>\nСписок: {ADMIN_IDS}")

@router.message(Command("myid"))
async def cmd_myid(m: Message):
    await m.answer(f"Твой ID: <code>{m.from_user.id}</code>")

@router.callback_query(F.data == "admin_stats")
async def cb_admin_stats(c: CallbackQuery):
    if not is_admin(c.from_user.id):
        await c.answer("🚫", show_alert=True)
        return
    total_accs = sum(len(u.get("accounts", [])) for u in users.values())
    total_rest = sum(len(d.get("rest_channels", [])) for u in users.values() for d in u.get("targets", {}).values())
    total_dm = sum(len(d.get("dm_channels", [])) for u in users.values() for d in u.get("targets", {}).values())
    total_sent = sum(u.get("sent", 0) for u in users.values())
    spamming = sum(1 for u in users.values() if u.get("spamming"))
    text = f"""📊 <b>Статистика</b>

👑 Админов: {len(ADMIN_IDS)}
👤 Юзеров: {len(users)}
🔑 Токенов: {total_accs}
🖥 REST: {total_rest}
📱 DM: {total_dm}
📨 Отправлено: {total_sent}
🟢 Спамят: {spamming}"""
    try: await c.message.edit_text(text, reply_markup=back_kb())
    except: pass

@router.errors()
async def errors_handler(event):
    pass

async def main():
    print(f"👑 Админы: {ADMIN_IDS}")
    print(f"📁 Загружено юзеров: {len(users)}")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
```
