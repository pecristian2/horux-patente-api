from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx, re, asyncio
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
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-CL,es;q=0.9",
            "Referer": "https://www.patentechile.com/",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            # Primero cargar la página principal para obtener cookies
            await client.get("https://www.patentechile.com/", headers=headers)
            # Luego consultar la patente
            res = await client.get(
                f"https://www.patentechile.com/{patente}",
                headers=headers
            )

        if res.status_code != 200:
            return {"patente": patente, "encontrado": False, "error": f"HTTP {res.status_code}"}

        soup = BeautifulSoup(res.text, "html.parser")
        texto = soup.get_text(" ", strip=True)

        marca  = None
        modelo = None
        anio   = None
        dueno  = None

        # Patrones para extraer datos
        patrones = {
            "marca":  [r"Marca[:\s]+([A-Z][A-Za-z0-9\s\-]+?)(?:\s{2,}|Modelo|Año|$)", r'"marca"\s*:\s*"([^"]+)"'],
            "modelo": [r"Modelo[:\s]+([A-Z0-9][A-Za-z0-9\s\-\/]+?)(?:\s{2,}|Marca|Año|$)", r'"modelo"\s*:\s*"([^"]+)"'],
            "anio":   [r"A[ñn]o[:\s]+(\d{4})", r'"anio"\s*:\s*(\d{4})', r'"year"\s*:\s*(\d{4})'],
            "dueno":  [r"Propietario[:\s]+([A-ZÁÉÍÓÚ][A-Za-záéíóúñ\s]+?)(?:\s{2,}|RUT|$)", r'"propietario"\s*:\s*"([^"]+)"'],
        }

        for p in patrones["marca"]:
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                marca = m.group(1).strip()
                break

        for p in patrones["modelo"]:
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                modelo = m.group(1).strip()
                break

        for p in patrones["anio"]:
            m = re.search(p, res.text, re.IGNORECASE)
            if m:
                anio = m.group(1).strip()
                break

        for p in patrones["dueno"]:
            m = re.search(p, texto, re.IGNORECASE)
            if m:
                dueno = m.group(1).strip()
                break

        if not marca and not modelo:
            # Intentar desde JSON embebido en el HTML
            json_match = re.search(r'\{[^{}]*"patente"[^{}]*\}', res.text)
            if json_match:
                import json
                try:
                    data = json.loads(json_match.group())
                    marca  = data.get("marca") or data.get("make")
                    modelo = data.get("modelo") or data.get("model")
                    anio   = str(data.get("anio") or data.get("year") or "")
                    dueno  = data.get("propietario") or data.get("owner")
                except:
                    pass

        encontrado = bool(marca or modelo)
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
            "marca_modelo": marca_modelo,
        }

    except Exception as e:
        return {"patente": patente, "encontrado": False, "error": str(e)}
