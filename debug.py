import requests, re

url = "https://alpfederation.ru/mountainroute/1714/"
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})

print(f"🔍 Загружаю: {url}\n")
r = s.get(url, timeout=30)
html = r.text

# Поиск 1: Есть ли documents_files?
print("🔎 Поиск 'documents_files':")
if '"documents_files"' in html:
    pos = html.find('"documents_files"')
    print(f"✅ Найдено на позиции {pos}")
    print("\n📋 Фрагмент (+400 символов после):")
    print(html[pos:pos+400])
else:
    print("❌ Не найдено в HTML")

# Поиск 2: Пробуем разные паттерны
print("\n🔎 Паттерн 1: с запятой в конце")
p1 = r'"documents_files"\s*:\s*(\[.*?\]),'
m1 = re.search(p1, html, re.DOTALL)
print(f"Результат: {'✅ Найдено' if m1 else '❌ Нет'}")
if m1: print(m1.group(1)[:200])

print("\n🔎 Паттерн 2: без запятой")
p2 = r'"documents_files"\s*:\s*(\[.*?\])(?:,|\n|\s)'
m2 = re.search(p2, html, re.DOTALL)
print(f"Результат: {'✅ Найдено' if m2 else '❌ Нет'}")
if m2: print(m2.group(1)[:200])

print("\n🔎 Паттерн 3: просто ищем id + filename")
p3 = r'"id"\s*:\s*(\d+).*?"filename"\s*:\s*"([^"]+)"'
m3 = re.findall(p3, html, re.DOTALL)
print(f"Найдено пар: {len(m3)}")
for fid, fname in m3[:5]:
    print(f"  ID: {fid} → {fname}")

print("\n🔎 Бонус: есть ли 'api/files' в HTML?")
if 'api/files' in html:
    print("✅ Ссылки на API найдены")
    # Покажем контекст
    pos = html.find('api/files')
    print(html[max(0,pos-50):pos+100])
else:
    print("❌ Ссылки на API не найдены")