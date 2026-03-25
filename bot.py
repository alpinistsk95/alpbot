import os,re,json,logging,time,requests,asyncio
from aiogram import Bot,Dispatcher,types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()
TOKEN=os.getenv("BOT_TOKEN")
BASE=os.getenv("SITE_BASE_URL","https://alpfederation.ru")
PORT=int(os.getenv("PORT", 8080))

logging.basicConfig(level=logging.INFO)
log=logging.getLogger(__name__)

bot=Bot(token=TOKEN)
dp=Dispatcher()
s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
LR={}

# 🔒 WATCHDOG: время последнего сообщения
LAST_UPDATE_TIME = time.time()
MAX_IDLE_TIME = 300  # 5 минут без обновлений = перезагрузка

async def health_handler(request):
    return web.json_response({"status": "ok", "bot": "running"})

async def start_http_server():
    app = web.Application()
    app.router.add_get('/', health_handler)
    app.router.add_get('/health', health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    log.info(f"✅ HTTP сервер запущен на порту {PORT}")

def get_file_ids(route_id):
    url=f"{BASE}/api/mountainroutes/{route_id}"
    try:
        r=s.get(url,timeout=30)
        r.raise_for_status()
        data=r.json()
        files=[]
        docs=data.get("documents_files",[])
        if isinstance(docs,list):
            for item in docs:
                if isinstance(item,dict) and "id" in item:
                    files.append({
                        "id":item["id"],
                        "fn":item.get("original_name") or item.get("filename") or f"file_{item['id']}"
                    })
        return files
    except Exception as e:
        log.error(f"API error: {e}")
        return []

def dl(fid):
    """Скачивает файл с ПРАВИЛЬНОЙ обработкой кириллицы в имени"""
    resp=s.get(f"{BASE}/api/files/{fid}",timeout=30)
    resp.raise_for_status()
    cd=resp.headers.get("Content-Disposition","")
    
    nm = None
    
    # 🔑 Способ 1: filename* (RFC 5987) - UTF-8 encoded
    m = re.search(r"filename\*\s*=\s*UTF-8''([^;\s\"]+)", cd, re.IGNORECASE)
    if m:
        nm = requests.utils.unquote(m.group(1))
    
    # 🔑 Способ 2: обычное filename в кавычках (с декодированием кириллицы)
    if not nm:
        m = re.search(r'filename\s*=\s*"([^"]*)"', cd)
        if m:
            raw = m.group(1)
            # КЛЮЧЕВОЙ МОМЕНТ: декодируем из latin1 в UTF-8
            try:
                nm = raw.encode('latin1').decode('utf-8')
            except:
                nm = raw
    
    # 🔑 Способ 3: filename без кавычек
    if not nm:
        m = re.search(r'filename\s*=\s*([^\s;]+)', cd)
        if m:
            raw = m.group(1).strip()
            try:
                nm = raw.encode('latin1').decode('utf-8')
            except:
                nm = raw
    
    # Фоллбэк
    if not nm:
        nm = f"file_{fid}.pdf"
    
    # Очистка от опасных символов
    nm = re.sub(r'[<>:"/\\|?*]', '_', nm)
    
    return resp.content, nm

@dp.message(Command("start"))
async def start(m):
    await m.answer("👋 Пришли ссылку на маршрут.")

@dp.message()
async def on_msg(m):
    global LAST_UPDATE_TIME
    LAST_UPDATE_TIME = time.time()  # 🔒 Сбрасываем таймер watchdog
    
    uid=str(m.from_user.id);txt=m.text.strip()
    now=time.time()
    if uid in LR and now-LR[uid]<10:
        await m.answer("⏳ 10 сек пауза");return
    LR[uid]=now
    if not txt.startswith("http"):
        await m.answer("❌ Не ссылка");return
    if "alpfederation.ru" not in txt:
        await m.answer("❌ Только alpfederation.ru");return
    
    route_match=re.search(r'/(\d+)/?$',txt)
    if not route_match:
        await m.answer("❌ Не удалось найти ID маршрута");return
    route_id=route_match.group(1)
    
    st=await m.answer("🔍 Запрашиваю файлы...")
    
    files=get_file_ids(route_id)
    if not files:
        await st.edit_text("❌ Файлы не найдены")
        return
    
    await st.edit_text(f"📦 {len(files)}. Качаю...")
    ok=err=0
    for f in files:
        try:
            time.sleep(1)
            cnt,nm=dl(f["id"])
            if len(cnt)>48*1024*1024:
                await m.answer(f"⚠️ {nm} >50MB");err+=1;continue
            await m.answer_document(document=BufferedInputFile(file=cnt,filename=nm),caption=f"📄 {nm}")
            ok+=1
        except requests.HTTPError as e:
            await m.answer(f"❌ {f['id']}: {e.response.status_code}");err+=1
        except Exception as e:
            await m.answer(f"❌ {e}");err+=1
    await st.edit_text(f"✅ Готово! OK:{ok} Err:{err}")

# 🔒 WATCHDOG: проверка на зависание
async def check_health():
    while True:
        await asyncio.sleep(60)
        if time.time() - LAST_UPDATE_TIME > MAX_IDLE_TIME:
            log.warning("⚠️ Бот не получает обновления 5 мин! Перезапуск...")
            os._exit(1)

async def main():
    await start_http_server()
    asyncio.create_task(check_health())  # 🔒 Запускаем сторожа
    log.info("🚀 Запуск бота...")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())