from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx, re, asyncio, random
from bs4 import BeautifulSoup

app = FastAPI(title="HORUX Patente API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok", "service": "HORUX Patente API"}

@app.get("/patente/{patente}")
async def consultar_patente(patente: str):
    patente = patente.upper().strip()
    
    urls = [
        f"https://www.patentechile.com/{patente}",
        f"https://www.patentechile.com/consulta/{patente}",
        f"https://www.patentechile.com/?patente={patente}",
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.google.com/",
    }

    try:
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers=headers,
        ) as client:
            # Simular visita previa a Google
            await asyncio.sleep(random.uniform(0.5, 1.5))
            
            # Visitar home primero para obtener cookies
            try:
                r0 = await client.get("https://www.patentechile.com/", headers=headers)
                await asyncio.sleep(random.uniform(0.5, 1.0))
            except:
                pass

            # Intentar distintas URLs
            res = None
            for url in urls:
                try:
                    r = await client.get(url, headers={**headers, "Referer": "https://www.patentechile.com/"})
                    if r.status_code == 200 and len(r.text) > 500:
                        res = r
                        break
                except:
                    continue

            if not res:
                # Intentar con POST si GET no funciona
                try:
                    res = await client.post(
                        "https://www.patentechile.com/",
                        data={"patente": patente},
                        headers={**headers, "Content-Type": "application/x-www-form-urlencoded"},
                    )
                except:
                    pass

        if not res or res.status_code != 200:
            status = res.status_code if res else "sin respuesta"
            return {"patente": patente, "encontrado": False, "error": f"HTTP {status}"}

        html = res.text
        soup = BeautifulSoup(html, "lxml")
        texto = soup.get_text(" ", strip=True)

        marca = modelo = anio = dueno = rut = None

        # Buscar en JSON embebido
        for json_pat in [
            r'\{[^{}]*"marca"[^{}]*\}',
            r'\{[^{}]*"make"[^{}]*\}',
            r'application/json[^>]*>(\{[^<]+\})',
        ]:
            m = re.search(json_pat, html, re.IGNORECASE)
            if m:
                import json
                try:
                    data = json.loads(m.group() if '{' in m.group(0)[:5] else m.group(1))
                    marca  = data.get("marca") or data.get("make")
                    modelo = data.get("modelo") or data.get("model")
                    anio   = str(data.get("anio") or data.get("year") or "")
                    dueno  = data.get("propietario") or data.get("owner") or data.get("nombre")
                    rut    = data.get("rut")
                    if marca: break
                except:
                    pass

        # Buscar en texto plano
        if not marca:
            for p in [r"Marca[:\s]+([A-ZÁÉÍÓÚ][A-Za-záéíóúñ0-9\s\-]+?)(?:\s{2,}|Modelo|Año|RUT|$)", r'"marca"\s*:\s*"([^"]+)"']:
                m = re.search(p, texto, re.IGNORECASE)
                if m:
                    val = m.group(1).strip()
                    if len(val) > 1 and val.lower() not in ['patente','consulta']:
                        marca = val; break

        if not modelo:
            for p in [r"Modelo[:\s]+([A-Z0-9][A-Za-z0-9\s\-\/]+?)(?:\s{2,}|Marca|Año|RUT|$)", r'"modelo"\s*:\s*"([^"]+)"']:
                m = re.search(p, texto, re.IGNORECASE)
                if m:
                    modelo = m.group(1).strip(); break

        if not anio:
            for p in [r"A[ñn]o[:\s]+(\d{4})", r'"anio"\s*:\s*(\d{4})', r'"year"\s*:\s*(\d{4})']: 
                m = re.search(p, html, re.IGNORECASE)
                if m:
                    anio = m.group(1); break

        if not dueno:
            for p in [r"Propietario[:\s]+([A-ZÁÉÍÓÚ][A-Za-záéíóúñ\s]+?)(?:\s{2,}|RUT|Marca|$)", r'"propietario"\s*:\s*"([^"]+)"']:
                m = re.search(p, texto, re.IGNORECASE)
                if m:
                    dueno = m.group(1).strip(); break

        encontrado = bool(marca or modelo or dueno)
        marca_modelo = None
        if marca or modelo:
            partes = [p for p in [marca, modelo] if p]
            marca_modelo = "/".join(partes)
            if anio:
                marca_modelo += f" ({anio})"

        return {
            "patente":      patente,
            "encontrado":   encontrado,
            "marca":        marca,
            "modelo":       modelo,
            "anio":         anio,
            "dueno":        dueno,
            "rut":          rut,
            "marca_modelo": marca_modelo,
            "html_length":  len(html),
        }

    except Exception as e:
        return {"patente": patente, "encontrado": False, "error": str(e)}
