import os,re,json,logging,time,requests
from aiogram import Bot,Dispatcher,types
from aiogram.filters import Command
from aiogram.types import BufferedInputFile
from dotenv import load_dotenv

load_dotenv()
TOKEN=os.getenv("BOT_TOKEN")
BASE=os.getenv("SITE_BASE_URL","https://alpfederation.ru")

logging.basicConfig(level=logging.INFO)
log=logging.getLogger(__name__)

bot=Bot(token=TOKEN)
dp=Dispatcher()
s=requests.Session()
s.headers.update({"User-Agent":"Mozilla/5.0"})
LR={}

def get_file_ids(route_id):
    """Запрашиваем файлы с правильного API эндпоинта"""
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
    """Скачиваем файл с /api/files/{ID}"""
    resp=s.get(f"{BASE}/api/files/{fid}",timeout=30)
    resp.raise_for_status()
    cd=resp.headers.get("Content-Disposition","")
    m=re.search(r'filename\*?="?([^";\n]+)"?',cd)
    nm=m.group(1).strip('"') if m else f"{fid}.pdf"
    return resp.content,re.sub(r'[<>:"/\\|?*]','_',nm)

@dp.message(Command("start"))
async def start(m):await m.answer("👋 Пришли ссылку на маршрут.")

@dp.message()
async def on_msg(m):
    uid=str(m.from_user.id);txt=m.text.strip()
    now=time.time()
    if uid in LR and now-LR[uid]<10:
        await m.answer("⏳ 10 сек пауза");return
    LR[uid]=now
    if not txt.startswith("http"):await m.answer("❌ Не ссылка");return
    if "alpfederation.ru" not in txt:await m.answer("❌ Только alpfederation.ru");return
    
    # Извлекаем ID маршрута из URL (например, /mountainroute/1714/ → 1714)
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

async def main():
    log.info("🚀 Запуск...")
    await dp.start_polling(bot)

if __name__=="__main__":
    import asyncio;asyncio.run(main())