import re
import json
import asyncio
import requests
from typing import Optional, Any
from datetime import datetime
from colorama import init, Fore, Style
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from fastapi import FastAPI, Query, HTTPException, status
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn
from bs4 import BeautifulSoup

# Colorama ve Rich başlat
init(autoreset=True)
console = Console()

# --------------------------- KONFİG ---------------------------
API_TITLE = "Rivex Sorgulama API - Moon Edition"
API_VERSION = "2035.7.0"

# Rivex API endpoint'leri (gerçek API yolu)
API_ENDPOINTS = {
    "tcsorgu": "https://rivex.lol/api/req/tc.php",
    "adsoyad": "https://rivex.lol/api/req/adsoyad.php",
    "gsmtc": "https://rivex.lol/api/req/gsmtc.php",
    "tcgsm": "https://rivex.lol/api/req/tcgsm.php",
    "aile": "https://rivex.lol/api/req/aile.php",
    "sulale": "https://rivex.lol/api/req/sulale.php"
}

# Referer için sayfa URL'leri
PAGE_ENDPOINTS = {
    "tcsorgu": "https://rivex.lol/tcsorgu.php",
    "adsoyad": "https://rivex.lol/adsoyad.php",
    "gsmtc": "https://rivex.lol/gsmtc.php",
    "tcgsm": "https://rivex.lol/tcgsm.php",
    "aile": "https://rivex.lol/aile.php",
    "sulale": "https://rivex.lol/sülale.php"
}

TIMEOUT = 30  # saniye

# --------------------------- MODELLER (Pydantic V2 Uyumlu) ---------------------------
class SorguRequest(BaseModel):
    query: str = Field(
        ..., 
        description="Sorgu değeri (TC, Ad Soyad, GSM vb.)",
        json_schema_extra={"example": "12345678901"}
    )

class SorguResponse(BaseModel):
    success: bool
    data: Optional[Any] = None  # Direkt veri
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    source: str = "Rivex.lol"

# --------------------------- FASTAPI UYGULAMASI ---------------------------
app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="2035 Moon Evreni Gelişmiş TC Sorgulama API - Rivex.lol üzerinden sorgular.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS - Herkese açık
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------- HTTP İSTEK SORGULAMA ---------------------------
async def sorgula_with_session(query: str, api_url: str, page_url: str, param_name: str = "tckn") -> dict:
    """Session ile Rivex API'sine direkt istek atar."""
    try:
        session = requests.Session()
        
        # Önce sayfayı ziyaret et (cookie almak için)
        headers_page = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        session.get(page_url, headers=headers_page, timeout=TIMEOUT)
        
        # Şimdi API'ye istek at
        headers_api = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        
        # GET isteği
        params = {param_name: query}
        response = session.get(api_url, params=params, headers=headers_api, timeout=TIMEOUT)
        
        # JSON yanıtı kontrol et
        try:
            json_data = response.json()
            return {
                "success": True,
                "json": json_data,
                "text": response.text,
                "method": "http_json"
            }
        except:
            # JSON değilse HTML parse et
            return {
                "success": True,
                "text": response.text,
                "method": "http_html"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"HTTP hatası: {str(e)}"
        }

# --------------------------- SENKRON SORGULAMA ---------------------------
def sorgula_senkron(query: str, api_url: str, page_url: str, param_name: str = "tckn") -> dict:
    """Senkron HTTP isteği."""
    try:
        session = requests.Session()
        
        headers_page = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        session.get(page_url, headers=headers_page, timeout=TIMEOUT)
        
        headers_api = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        
        # POST ile gönder
        data = {param_name: query}
        response = session.post(api_url, data=data, headers=headers_api, timeout=TIMEOUT)
        
        console.print(f"[bold red]📊 Status: {response.status_code}, Response length: {len(response.text)}[/bold red]")
        
        try:
            json_data = response.json()
            console.print(f"[bold red]📦 JSON: {json.dumps(json_data, ensure_ascii=False)[:500]}[/bold red]")
            return {
                "success": True,
                "json": json_data,
                "text": response.text,
                "method": "http_json"
            }
        except:
            console.print(f"[bold red]📄 HTML: {response.text[:300]}[/bold red]")
            return {
                "success": True,
                "text": response.text,
                "method": "http_html"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"HTTP hatası: {str(e)}"
        }

# --------------------------- ASENKRON SORGULAMA ---------------------------
async def sorgula_async(query: str, api_url: str, page_url: str, param_name: str = "tckn") -> dict:
    """Asenkron HTTP isteği."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sorgula_senkron, query, api_url, page_url, param_name)

# --------------------------- AD SOYAD İÇİN ÖZEL FONKSIYON ---------------------------
def sorgula_adsoyad_senkron(ad: str, soyad: str, api_url: str, page_url: str) -> dict:
    """Ad soyad için özel senkron HTTP isteği."""
    try:
        session = requests.Session()
        
        headers_page = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        session.get(page_url, headers=headers_page, timeout=TIMEOUT)
        
        headers_api = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": page_url,
            "X-Requested-With": "XMLHttpRequest",
        }
        
        # Ad ve soyad ayrı parametreler - POST ile dene
        data = {"ad": ad, "soyad": soyad}
        
        # Debug için
        console.print(f"[bold magenta]🌐 POST to {api_url} with data: {data}[/bold magenta]")
        
        response = session.post(api_url, data=data, headers=headers_api, timeout=TIMEOUT)
        
        try:
            json_data = response.json()
            return {
                "success": True,
                "json": json_data,
                "text": response.text,
                "method": "http_json"
            }
        except:
            return {
                "success": True,
                "text": response.text,
                "method": "http_html"
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"HTTP hatası: {str(e)}"
        }

async def sorgula_adsoyad_async(ad: str, soyad: str, api_url: str, page_url: str) -> dict:
    """Ad soyad için özel asenkron HTTP isteği."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sorgula_adsoyad_senkron, ad, soyad, api_url, page_url)


# --------------------------- TABLO PARSE EDİCİ ---------------------------
def extract_javascript_data(html: str) -> dict:
    """HTML içindeki JavaScript değişkenlerinden veriyi çıkarır."""
    data = {}
    
    # Tüm olası formatları dene
    patterns = [
        r'const\s+d\s*=\s*JSON\.parse\([\'"`](.+?)[\'"`]\)',
        r'let\s+d\s*=\s*JSON\.parse\([\'"`](.+?)[\'"`]\)',
        r'var\s+d\s*=\s*JSON\.parse\([\'"`](.+?)[\'"`]\)',
        r'const\s+d\s*=\s*({[^;]+})',
        r'let\s+d\s*=\s*({[^;]+})',
        r'var\s+d\s*=\s*({[^;]+})',
        r'd\s*=\s*({[^;]+})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, html, re.DOTALL)
        for match in matches:
            try:
                if match.startswith('{'):
                    # Direkt obje
                    data = json.loads(match)
                else:
                    # JSON string
                    json_str = match.replace('\\', '').replace('\n', '').replace('\r', '')
                    data = json.loads(json_str)
                
                if data:
                    return data
            except:
                continue
    
    return data

def extract_table_data(html: str) -> dict:
    """HTML'den tablo verilerini çıkarır. Template literal varsa doldurur, yoksa direkt değeri alır."""
    result = {
        "tables": [],
        "parsed_data": {},
        "raw_data": {}
    }
    
    # JavaScript değişkenlerinden veriyi çıkar
    js_data = extract_javascript_data(html)
    if js_data:
        result["raw_data"] = js_data
    
    # Tüm tabloları bul
    table_matches = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    
    for table_html in table_matches:
        rows = []
        # Satırları bul
        row_matches = re.findall(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL | re.IGNORECASE)
        
        for row_html in row_matches:
            cells = []
            # Hücreleri bul (th veya td)
            cell_matches = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL | re.IGNORECASE)
            
            for cell in cell_matches:
                cell_text = cell
                
                # Eğer template literal varsa
                if '${' in cell_text:
                    if js_data:
                        # JavaScript template literal varsa ve js_data varsa doldur
                        def replace_template(match):
                            template = match.group(1)
                            
                            # d.FIELD || 'default' formatını parse et
                            field_match = re.search(r'd\.(\w+)', template)
                            if field_match:
                                field_name = field_match.group(1)
                                value = js_data.get(field_name, '')
                                
                                if value and value != '':
                                    return str(value)
                                elif '||' in template:
                                    # Default değeri al
                                    default_match = re.search(r"\|\|\s*['\"]([^'\"]*)['\"]", template)
                                    if default_match:
                                        return default_match.group(1)
                            
                            return ''
                        
                        cell_text = re.sub(r'\$\{([^}]+)\}', replace_template, cell_text)
                    else:
                        # js_data yoksa template literal'ı kaldır, default değeri kullan
                        def get_default(match):
                            template = match.group(1)
                            if '||' in template:
                                default_match = re.search(r"\|\|\s*['\"]([^'\"]*)['\"]", template)
                                if default_match:
                                    return default_match.group(1)
                            return ''
                        
                        cell_text = re.sub(r'\$\{([^}]+)\}', get_default, cell_text)
                
                # HTML etiketlerini temizle
                clean_text = re.sub(r'<[^>]+>', '', cell_text)
                clean_text = clean_text.strip()
                # HTML entity'lerini decode et
                clean_text = clean_text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&quot;', '"')
                clean_text = clean_text.replace('&#39;', "'").replace('&lt;', '<').replace('&gt;', '>')
                # Fazla boşlukları temizle
                clean_text = ' '.join(clean_text.split())
                cells.append(clean_text)
            
            if cells:  # Boş satırları ekleme
                rows.append(cells)
        
        if rows:  # Boş tabloları ekleme
            result["tables"].append(rows)
    
    # Parsed data - anahtar-değer çiftleri olarak (daha kolay kullanım)
    if result["tables"]:
        for table in result["tables"]:
            for row in table:
                if len(row) == 2:
                    key = row[0].strip()
                    value = row[1].strip()
                    if value:  # Boş değerleri ekleme
                        result["parsed_data"][key] = value
    
    return result

# --------------------------- API ENDPOINTLERİ ---------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    return """
    <html>
        <head><title>🚀 Rivex Sorgulama API - Moon 2035</title>
        <style>
            body { background: #0b0e14; color: #00ffcc; font-family: 'Courier New', monospace; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; }
            .box { background: #1a1f2b; padding: 40px; border-radius: 20px; border: 2px solid #00ffcc; box-shadow: 0 0 30px #00ffcc55; text-align: center; max-width: 700px; }
            h1 { color: #ffaa00; text-shadow: 0 0 15px #ffaa00; }
            h2 { color: #00ffcc; }
            .endpoint { background: #0b0e14; padding: 10px; border-radius: 8px; border: 1px solid #ffaa00; margin: 10px 0; text-align: left; }
            .endpoint strong { color: #ffaa00; }
            a { color: #00ffcc; text-decoration: none; font-weight: bold; }
            a:hover { color: #ffaa00; }
            .footer { margin-top: 30px; font-size: 12px; color: #888; }
            .status { color: #00ff88; }
        </style>
        </head>
        <body>
            <div class="box">
                <h1>🌀 destroyerr1558 Advanced Code Creator</h1>
                <h2>🔍 Rivex Multi Sorgulama API</h2>
                
                <div class="endpoint"><strong>POST/GET</strong> /tcsorgu?query=12345678901</div>
                <div class="endpoint"><strong>POST/GET</strong> /adsoyad?query=Ali Veli</div>
                <div class="endpoint"><strong>POST/GET</strong> /gsmtc?query=05551234567</div>
                <div class="endpoint"><strong>POST/GET</strong> /tcgsm?query=12345678901</div>
                <div class="endpoint"><strong>POST/GET</strong> /aile?query=12345678901</div>
                <div class="endpoint"><strong>POST/GET</strong> /sulale?query=12345678901</div>
                
                <p>📘 Dökümantasyon: <a href="/docs">/docs</a> | <a href="/redoc">/redoc</a></p>
                <p><span class="status">✅ API Aktif - Moon Evreni 2035</span></p>
                <div class="footer">⚡ Her türlü kod burada üretilir ⚡</div>
            </div>
        </body>
    </html>
    """

# Genel sorgulama fonksiyonu
async def genel_sorgula(endpoint_name: str, query: str):
    """Herhangi bir endpoint için sorgulama yapar."""
    if endpoint_name not in API_ENDPOINTS:
        raise HTTPException(status_code=404, detail=f"Endpoint '{endpoint_name}' bulunamadı")
    
    api_url = API_ENDPOINTS[endpoint_name]
    page_url = PAGE_ENDPOINTS[endpoint_name]
    
    # Parametre adını belirle
    param_map = {
        "tcsorgu": "tckn",
        "adsoyad": "adsoyad",  # Özel işlem gerekecek
        "gsmtc": "gsm",
        "tcgsm": "tckn",
        "aile": "tckn",
        "sulale": "tckn"
    }
    param_name = param_map.get(endpoint_name, "tckn")
    
    console.print(f"[bold cyan]📥 {endpoint_name} sorgu (HTTP): {query}[/bold cyan]")
    
    # Ad soyad için özel işlem
    if endpoint_name == "adsoyad":
        parts = query.strip().split(maxsplit=1)
        ad = parts[0] if len(parts) > 0 else ""
        soyad = parts[1] if len(parts) > 1 else ""
        
        console.print(f"[bold yellow]🔍 Ad: '{ad}', Soyad: '{soyad}'[/bold yellow]")
        
        # En az biri boş olmamalı
        if not ad and not soyad:
            return SorguResponse(
                success=False,
                error="En az ad veya soyad girilmelidir"
            )
        
        # Özel sorgulama fonksiyonu çağır
        raw = await sorgula_adsoyad_async(ad, soyad, api_url, page_url)
    else:
        raw = await sorgula_async(query, api_url, page_url, param_name)
    
    if not raw.get("success"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=raw.get("error", "Sorgulama başarısız")
        )
    
    # JSON yanıt varsa temizle ve döndür
    if "json" in raw:
        json_data = raw["json"]
        
        # Sadece istenen alanları filtrele
        allowed_fields = [
            "TC", "AD", "SOYAD", "GSM", "BABAADI", "BABATC", 
            "ANNEADI", "ANNETC", "DOGUMTARIHI", "OLUMTARIHI", "DOGUMYERI",
            "MEMLEKETIL", "MEMLEKETILCE", "MEMLEKETKOY", "ADRESIL", "ADRESILCE",
            "AILESIRANO", "BIREYSIRANO", "MEDENIHAL", "CINSIYET", "YAS", "ADRES"
        ]
        
        # Eğer data array ise her bir öğeyi filtrele
        if isinstance(json_data, dict) and "data" in json_data:
            if isinstance(json_data["data"], list):
                filtered_data = []
                for item in json_data["data"]:
                    filtered_item = {k: v for k, v in item.items() if k in allowed_fields}
                    filtered_data.append(filtered_item)
                return SorguResponse(
                    success=True,
                    data=filtered_data
                )
            else:
                # Tek bir obje
                filtered = {k: v for k, v in json_data["data"].items() if k in allowed_fields}
                return SorguResponse(
                    success=True,
                    data=filtered
                )
        else:
            # Direkt obje veya farklı format - hatayı da göster
            if isinstance(json_data, dict) and json_data.get("success") == False:
                return SorguResponse(
                    success=False,
                    error=json_data.get("message", "Bilinmeyen hata")
                )
            
            return SorguResponse(
                success=True,
                data=json_data
            )
    
    # HTML ise tabloları çıkar
    result = extract_table_data(raw.get("text", ""))
    
    return SorguResponse(
        success=True,
        data=result if (result.get("tables") or result.get("parsed_data")) else None
    )

# TC Sorgu
@app.post("/tcsorgu", response_model=SorguResponse)
async def tcsorgu_post(request: SorguRequest):
    return await genel_sorgula("tcsorgu", request.query)

@app.get("/tcsorgu", response_model=SorguResponse)
async def tcsorgu_get(query: str = Query(..., description="TC Kimlik No")):
    return await genel_sorgula("tcsorgu", query)

# Ad Soyad Sorgu
@app.post("/adsoyad", response_model=SorguResponse)
async def adsoyad_post(request: SorguRequest):
    return await genel_sorgula("adsoyad", request.query)

@app.get("/adsoyad", response_model=SorguResponse)
async def adsoyad_get(query: str = Query(..., description="Ad Soyad")):
    return await genel_sorgula("adsoyad", query)

# GSM'den TC Sorgu
@app.post("/gsmtc", response_model=SorguResponse)
async def gsmtc_post(request: SorguRequest):
    return await genel_sorgula("gsmtc", request.query)

@app.get("/gsmtc", response_model=SorguResponse)
async def gsmtc_get(query: str = Query(..., description="GSM Numarası")):
    return await genel_sorgula("gsmtc", query)

# TC'den GSM Sorgu
@app.post("/tcgsm", response_model=SorguResponse)
async def tcgsm_post(request: SorguRequest):
    return await genel_sorgula("tcgsm", request.query)

@app.get("/tcgsm", response_model=SorguResponse)
async def tcgsm_get(query: str = Query(..., description="TC Kimlik No")):
    return await genel_sorgula("tcgsm", query)

# Aile Sorgu
@app.post("/aile", response_model=SorguResponse)
async def aile_post(request: SorguRequest):
    return await genel_sorgula("aile", request.query)

@app.get("/aile", response_model=SorguResponse)
async def aile_get(query: str = Query(..., description="TC Kimlik No")):
    return await genel_sorgula("aile", query)

# Sülale Sorgu
@app.post("/sulale", response_model=SorguResponse)
async def sulale_post(request: SorguRequest):
    return await genel_sorgula("sulale", request.query)

@app.get("/sulale", response_model=SorguResponse)
async def sulale_get(query: str = Query(..., description="TC Kimlik No")):
    return await genel_sorgula("sulale", query)

@app.get("/health", tags=["Sistem"])
async def health():
    return {
        "status": "online", 
        "version": API_VERSION, 
        "timestamp": datetime.now().isoformat(),
        "moon_evreni": "aktif",
        "kod_uretici": "destroyerr1558",
        "endpoints": list(API_ENDPOINTS.keys())
    }

# --------------------------- BAŞLATMA ---------------------------
if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    
    console.print(Panel.fit(
        f"[bold magenta]🚀 destroyerr1558 Advanced Code Creator[/bold magenta]\n"
        f"[cyan]Rivex Multi Sorgulama API - Moon Evreni 2035[/cyan]\n"
        f"[yellow]📍 http://0.0.0.0:{port}[/yellow]\n"
        f"[green]📘 Dökümantasyon: /docs[/green]\n"
        f"[blue]🔧 6 Endpoint Aktif: {', '.join(API_ENDPOINTS.keys())}[/blue]",
        border_style="bright_blue"
    ))

    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )
