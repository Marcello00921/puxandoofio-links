"""Gera index.html (página da bio do Puxando o Fio) a partir de produtos.json + os 8 produtos dos vídeos.

Uso:  python _gerar.py            -> reescreve index.html
      python _gerar.py --conferir -> só confere (rc 1 se faltar título curto, categoria ou link)

produtos.json fica FORA do commit (traz comissão e notas internas; o repo é público). A origem dele é a
coleta da central de afiliados registrada em agrodoc/tools/explicador/afiliado_links.md (09/10/2026).
O prefixo "_" deixa este arquivo fora do site publicado pelo GitHub Pages (Jekyll ignora "_*").

Regras da página (pedido do Marcello, 09/10, boost da landing no TikTok):
- sem preço fixo ("ver preço no Mercado Livre"): preço muda e anúncio pago com preço velho engana;
- #publi + aviso de afiliado + rótulo de IA do canal visíveis no topo;
- foto real do anúncio (mlstatic, variante quadrada 320 px), sem editar;
- sem script de terceiro, sem cookie, sem pop-up.

Contador (12/10, meta do Marcello: o 1º R$ de afiliado sem mão dele; o funil de 12/10 não via visita nem clique):
- Abacus (abacus.jasoncameron.dev, docs lidas em 12/10): grátis, sem cadastro, sem chave para /hit e /get, CORS
  aberto, sem cookie; limite de 30 pedidos/10 s por IP; a chave expira em 6 meses sem acesso (cada acesso renova).
  Não há script de terceiro: a página faz um `fetch` GET em /hit/<NS>/visita ao abrir e /hit/<NS>/c-<código> no
  clique. O pedido leva o IP de quem visita ao Abacus (como qualquer pedido HTTP); a página não manda nada além do
  nome do contador.
- Clique: `fetch(..., {keepalive: true})` SEM preventDefault, então o link segue mesmo com o contador fora do ar.
- NS de produção abaixo; o teste (agrodoc tools/explicador/vitrine_contador.py --teste-navegador) gera a página com
  NS_TESTE numa pasta temporária, para não sujar o contador de produção.

Bloco "Do vídeo mais recente" (12/10): quem vem da bio do TikTok procura o produto do vídeo que acabou de ver. A fonte
é o log de post da esteira (agrodoc dados/esteira/log.jsonl: motivo "postou", rc 0, tema af_*), com o link da fila
(dados/esteira/fila.json, link_ml) ou da pauta (tools/explicador/pauta_v2.json, link_ml). Só entra produto que JÁ está
na página (passou pelo filtro da vitrine). Sem o agrodoc ao lado, o bloco não aparece. O bloco é fotografia da hora
em que o gerador rodou: depois de um post novo, gerar de novo e empurrar.
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
AGRODOC = AQUI.parents[2]          # saida/explicador/puxandoofio-links → agrodoc
CONTADOR = "https://abacus.jasoncameron.dev"
NS = "puxandoofio-links"
NS_TESTE = "puxandoofio-links-teste"
RECENTES = 3

# Categorias da página, na ordem dos chips.
CATS = {
    "eletronicos": "Eletrônicos",
    "eletrodomesticos": "Eletrodomésticos",
    "cozinha": "Cozinha",
    "casa": "Casa e jardim",
    "ferramentas": "Ferramentas",
    "automotivo": "Automotivo e moto",
    "esporte": "Esporte",
    "games": "Games e lazer",
    "escritorio": "Escritório e estudo",
    "beleza": "Beleza",
    "pet": "Pet",
}

# Os 8 que os vídeos citam ("o link está na bio"): ficam no topo e não podem sair.
# Foto = og:image do anúncio, lida no Chrome logado em 09/10/2026.
DOS_VIDEOS = [
    ("1rwicCP", "Moedor de café Hamilton Beach", "cozinha", "MLB-6464776800",
     "https://http2.mlstatic.com/D_NQ_NP_917113-MLU78264983537_082024-O.webp"),
    ("2iEuBq9", "Torneira gourmet Camperluz", "cozinha", "MLB-5742201726",
     "https://http2.mlstatic.com/D_NQ_NP_604316-MLA95535920196_102025-O.webp"),
    ("26ar6rh", "Multiprocessador 2 litros, inox", "cozinha", "MLB-7410017304",
     "https://http2.mlstatic.com/D_NQ_NP_868686-MLB116670449725_082026-O.webp"),
    ("1AScefL", "Chuveiro Lorenzetti Acqua Century Digital", "casa", "MLB-6202548554",
     "https://http2.mlstatic.com/D_NQ_NP_968461-MLA100009186845_122025-O.webp"),
    ("1iwbe8W", "Secador Philco com motor BLDC", "beleza", "MLB-6486861240",
     "https://http2.mlstatic.com/D_NQ_NP_723697-MLA115636981336_092026-O.webp"),
    ("1wiSSWV", "Caixa de som JBL Charge 6", "eletronicos", "MLB-5163844297",
     "https://http2.mlstatic.com/D_NQ_NP_966745-MLA109736095781_032026-O.webp"),
    ("18jgmtM", "Cooktop de indução Itatiaia", "eletrodomesticos", "MLB-5507107524",
     "https://http2.mlstatic.com/D_NQ_NP_975067-MLA112250309002_062026-O.webp"),
    ("2fu22GV", "Ar-condicionado LG Inverter", "eletrodomesticos", "MLB-5245309349",
     "https://http2.mlstatic.com/D_NQ_NP_751254-MLA111545505029_052026-O.webp"),
]
COM_POST = {"1rwicCP", "2iEuBq9", "26ar6rh", "1AScefL"}  # moedor, torneira, multiprocessador, chuveiro

# Título curto (sem promessa do vendedor: "sem CNH", "tira atraso", "antimofo", "original"...) e categoria,
# por código do meli.la. None = fora da página, com a razão.
CURTO = {
    "2bHdFbq": ("Scooter elétrica Xplore 500 W", "esporte"),
    "26uyPHY": ("Caixa de som JBL Boombox 4", "eletronicos"),
    "1bqYJz9": ("Notebook Acer ANV15 com RTX 4050", "escritorio"),
    "1TfXDuo": ("Smart TV Philco 50\" 4K Roku TV", "eletronicos"),
    "1bQVXJE": ("Máquina de lavar Electrolux 13 kg", "eletrodomesticos"),
    "2GvvMze": ("Esteira ergométrica dobrável", "esporte"),
    "2sxN6N2": ("Notebook ASUS Vivobook Go 15, Ryzen 5", "escritorio"),
    "31yHAFH": ("Parafusadeira e chave de impacto GDX 18V-285, 2 baterias", "ferramentas"),
    "1CPQeFQ": ("Kit guitarra Stratocaster para iniciante", "games"),
    "1UfDpUm": ("Perfume 212 VIP Rosé, Carolina Herrera, 125 ml", "beleza"),
    "1CJZpoH": ("Macaco hidráulico jacaré 2 t Bovenau", "automotivo"),
    "1EecBV9": ("Tablet Galaxy Tab S10 Lite, 128 GB", "eletronicos"),
    "1Bi5WCz": ("Módulo de pedal acelerador Shiftpower", "automotivo"),
    "1ZDEeYn": ("Cadeirinha infantil para carro, 0 a 36 kg", "automotivo"),
    "2cvPLrm": ("Cabeçote EA111 1.0 (Gol, Fox, Voyage)", "automotivo"),
    "2tkT5ta": ("Cooktop de indução Midea, 4 bocas", "eletrodomesticos"),
    "1AnjHFB": ("Armário de cozinha Itatiaia, 8 portas, aço", "cozinha"),
    "1MDEsCn": ("Smart TV TCL 65\" Mini LED 4K", "eletronicos"),
    "19dEUfK": ("2 pneus 175/75 R14 Doublestar", "automotivo"),
    "2Lw352S": ("Cooktop de indução EOS, 5 bocas, 90 cm", "eletrodomesticos"),
    "1prjxKE": ("Kit 4 ferramentas sem fio 48 V, 2 baterias", "ferramentas"),
    "22fXv6p": ("Fogão Electrolux 5 bocas, mesa de vidro", "eletrodomesticos"),
    "2dj8cD6": ("Cadeira gamer Xtreme Gamers reclinável", "games"),
    "1wnLu4C": ("Cadeira gamer Nitro", "games"),
    "2ce9rap": ("Bomba de ar elétrica portátil para pneu", "automotivo"),
    "1oAh8DB": ("Jogo de panelas Brinox Ceramic Life, 8 peças", "cozinha"),
    "1hEudeT": ("Bicicleta de spinning, roda de 6 kg", "esporte"),
    "2THZXRJ": ("2 pneus 175/65 R14 Goodyear Kelly Edge", "automotivo"),
    "2XFq56p": ("Lavadora de alta pressão Vonder LAV 1600", "ferramentas"),
    "2UDwyp1": ("Geladeira Midea duplex 410 L", "eletrodomesticos"),
    "18XoGXZ": ("Ar-condicionado split Philco Inverter 9.000 BTUs", "eletrodomesticos"),
    "1cyXGyb": ("Aspirador vertical sem fio Electrolux Ergorapido", "eletrodomesticos"),
    "2UbrVFa": ("Câmera veicular dupla DDPAI N1", "automotivo"),
    "1mVoRgH": ("Armário de cozinha Dora, 10 portas", "cozinha"),
    "2SojsEp": ("Aerador chafariz 1 cv para lago", "casa"),
    "2LRrExA": ("Celular Motorola Moto G86 5G, 256 GB", "eletronicos"),
    "2CZHkCm": ("Controle para Xbox Series X|S", "games"),
    # 09/10: a foto do anúncio mostra a lâmina de três pontas; a política "Dangerous Products or Services" do
    # TikTok (abr/2025) veta "Blades, knives, or any such sharp objects" na landing, e a exceção de faca não lista o Brasil.
    "2jRxCVr": None,
    "24ghTLF": ("Controle DualSense PS5, branco", "games"),
    "2q9Qgq1": ("Viveiro para calopsita e papagaio", "pet"),
    "1mTQz2X": ("Geladeira Consul Frost Free 297 L", "eletrodomesticos"),
    "2bwrwEt": ("Triciclo elétrico drift 250 W", "esporte"),
    "1wKNYX1": ("Robô aspirador Velds 3 em 1", "eletrodomesticos"),
    "28fu5FJ": ("Mesa gamer 120 cm", "games"),
    "25uLCyz": ("Tênis Kappa Pulse RX de corrida", "esporte"),
    "31nTczz": ("Celular Poco X7 Pro 5G, 512 GB", "eletronicos"),
    "1AEvx6L": ("Máquina de solda inversora MIG 160 A, 3 em 1", "ferramentas"),
    "21tX1fd": ("Kit cilindro para Titan, Fan e Bros 150", "automotivo"),
    "244mHdZ": ("Desumidificador com compressor, 8 L/dia", "eletrodomesticos"),
    "1Hmbnbt": ("Jogo de panelas cerâmicas para indução, 10 peças", "cozinha"),
    "1v3Sg8a": ("Piscina playground dinossauro Intex", "games"),
    "2GJ81RE": ("Martelete perfurador rompedor 1.300 W", "ferramentas"),
    "2CoGgN6": None,  # 09/10 refutador: REVIEW saude_regulada na coleta; fora do anúncio pago
    "2wesnnh": ("Purificador de água Midea SlimPure", "eletrodomesticos"),
    "2HaDjRs": ("Rádio automotivo Pioneer com Bluetooth", "automotivo"),
    "2fCmEom": ("Kit frente Titan 2025 para CG 160", "automotivo"),
    "2qRKCGk": ("Lavadora de alta pressão portátil Soarfly", "ferramentas"),
    "1Yi6fky": ("Par de intercomunicadores Bluetooth para capacete", "automotivo"),
    "1dMnXoH": ("Tablet Lenovo Tab 10,1\", 64 GB", "eletronicos"),
    "26h1ykX": ("Perfume Club de Nuit Intense, Armaf, 105 ml", "beleza"),
    "32fHhDp": ("Soprador de ar 750 W para infláveis", "games"),
    "31NxnbM": ("Nível a laser verde, 12 linhas, com tripé", "ferramentas"),
    "1GfPhXz": ("Escrivaninha Athenas para estudo e home office", "escritorio"),
    "1JCnTgF": ("Tênis Kappa Pulse para academia", "esporte"),
    "2Xg36yo": ("Capacete Norisk Razor Speedmax", "automotivo"),
    "2AUhJLu": ("Lavadora de alta pressão Kärcher Compacta", "casa"),
    "1U82Amy": ("Kit 4 bicos injetores 1.6 (Gol, Fox, Polo, Golf)", "automotivo"),
    "2U8Aajb": ("Balcão Laura para forno e micro-ondas", "cozinha"),
    "1TGv8Ad": ("Kit 3 body splash masculino Barbours", "beleza"),
    "2orRQUj": ("Panificadora Gallant, 19 programas", "eletrodomesticos"),
    "1qQ7uEq": ("Fone sem fio soundcore Sport X20", "eletronicos"),
    "1KHbNSb": ("Impressora Epson EcoTank L1250", "escritorio"),
    "1QSyJmz": ("Cordão de luz strobo, 1.600 LEDs, 50 m", "casa"),
    "2NDu31L": ("Tonalizante Nouê Camuflage, castanho", "beleza"),
    "2zD7r9o": ("Guarda-roupa casal Malta, 6 portas", "casa"),
    "14Y6TNV": ("Caixa de areia fechada para gato, em aço", "pet"),
    "2nmP3FC": ("Piscina inflável Mor Splash Fun 2.400 L", "games"),
    "1mH7zn2": ("Palmeira artificial de 1 metro com vaso", "casa"),
    "2KawELS": None,  # 09/10 refutador: provável jogo pré-carregado (réplica/pirataria não descartada)
    "32AYhcg": ("Petisco Churu para gatos, kit com 6", "pet"),
}


def foto_320(url: str) -> str:
    """Variante quadrada 320x320 do mlstatic (~10 KB contra ~21 KB da original, medido 09/10)."""
    m = re.match(r"https://http2\.mlstatic\.com/D_NQ_NP_(\d+-ML[A-Z]\d+_\d+)-O\b.*\.webp$", url)
    if not m:
        raise ValueError(f"foto fora do padrão mlstatic: {url}")
    return f"https://http2.mlstatic.com/D_Q_NP_{m.group(1)}-V.webp"


def sem_acento(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def montar_itens():
    dados = json.loads((AQUI / "produtos.json").read_text(encoding="utf-8"))
    itens, fora, erros = [], [], []
    for cod, titulo, cat, mlb, foto in DOS_VIDEOS:
        # 09/10 · refutador: só 4 têm post publicado (grep '"publicado": true' saida/diretor/af_*/publicar.json);
        # selo "Do vídeo" em produto sem post é texto enganoso para anúncio pago
        itens.append({"cod": cod, "titulo": titulo, "cat": cat, "video": cod in COM_POST, "mlb": mlb, "foto": foto_320(foto)})
    vistos = {i["cod"] for i in itens}
    for p in dados:
        cod = p["link"].rsplit("/", 1)[-1]
        if cod not in CURTO:
            erros.append(f"sem título curto: {cod} {p['titulo'][:60]}")
            continue
        if CURTO[cod] is None:
            fora.append(p["titulo"])
            continue
        titulo, cat = CURTO[cod]
        if cat not in CATS:
            erros.append(f"categoria desconhecida {cat} em {cod}")
        if cod in vistos:
            erros.append(f"link repetido {cod}")
        vistos.add(cod)
        itens.append({"cod": cod, "titulo": titulo, "cat": cat, "video": False, "mlb": p["mlb"], "foto": foto_320(p["foto"])})
    sobra = set(CURTO) - {p["link"].rsplit("/", 1)[-1] for p in dados}
    if sobra:
        erros.append(f"títulos curtos sem produto: {sorted(sobra)}")
    return itens, fora, erros


def _cod(link) -> str:
    m = re.fullmatch(r"https://meli\.la/([A-Za-z0-9]+)", str(link or "").strip())
    return m.group(1) if m else ""


def recentes(itens, agrodoc: Path = AGRODOC, n: int = RECENTES) -> list:
    """Os últimos posts de afiliado (mais recente primeiro, um por produto) que estão na página.
    [{"cod", "tema", "postado"}]; sem log, lista vazia (o bloco some)."""
    try:
        fila = json.loads((agrodoc / "dados" / "esteira" / "fila.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        fila = {}
    its = fila.get("itens", fila) if isinstance(fila, dict) else fila
    its = its if isinstance(its, list) else list(its.values()) if isinstance(its, dict) else []
    link_fila = {i.get("tema"): _cod(i.get("link_ml")) for i in its if isinstance(i, dict) and i.get("tema")}
    try:
        pa = json.loads((agrodoc / "tools" / "explicador" / "pauta_v2.json").read_text(encoding="utf-8"))
        link_pauta = {"af_" + str(i.get("id")): _cod(i.get("link_ml"))
                      for i in (pa.get("afiliado_por_dentro") or {}).get("itens") or [] if isinstance(i, dict)}
    except (OSError, ValueError, AttributeError):
        link_pauta = {}
    na_pagina = {i["cod"] for i in itens}
    posts = []
    try:
        linhas = (agrodoc / "dados" / "esteira" / "log.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        linhas = []
    for s in linhas:
        try:
            x = json.loads(s)
        except ValueError:
            continue
        esc = x.get("escolhido") if isinstance(x, dict) else None
        tema = str((esc or {}).get("tema") or "") if isinstance(esc, dict) else ""
        if not tema.startswith("af_") or x.get("motivo") != "postou" or str(x.get("rc")) != "0" or not x.get("post_id"):
            continue
        cod = link_fila.get(tema) or link_pauta.get(tema) or ""
        if cod in na_pagina:
            posts.append({"cod": cod, "tema": tema, "postado": str(x.get("em") or "")})
    posts.sort(key=lambda p: p["postado"], reverse=True)
    out, vistos = [], set()
    for p in posts:
        if p["cod"] not in vistos:
            vistos.add(p["cod"])
            out.append(p)
    return out[:n]


CSS = """
:root{--papel:#ECE8E1;--cartao:#F7F4EE;--tinta:#1F1D1A;--graf:#2E2B27;--cinza:#5F584F;--linha:#D9D3C8;--fio:#A3121E;--fio-escuro:#5E0810}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--papel);color:var(--tinta);font-family:Georgia,"Times New Roman",serif;line-height:1.45;-webkit-text-size-adjust:100%}
.sans{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif}
main{max-width:1180px;margin:0 auto;padding:20px 16px 40px}
header{border-left:4px solid var(--fio);padding-left:12px;margin-bottom:14px}
h1{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:1.6rem;font-weight:800;letter-spacing:-.01em;margin:0;color:var(--graf)}
header p{margin:2px 0 0;color:var(--cinza);font-size:1rem}
.aviso{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:.86rem;background:var(--cartao);border:1px solid var(--linha);border-radius:6px;padding:9px 12px;margin:0 0 12px;color:var(--graf)}
.aviso strong{color:var(--fio)}
.barra{display:none;position:sticky;top:0;z-index:2;background:var(--papel);padding:8px 0 10px;margin:0 -16px 6px;padding-left:16px;padding-right:16px;border-bottom:1px solid var(--linha)}
.js .barra{display:block}
.busca{width:100%;font:inherit;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:1rem;padding:10px 12px;border:1px solid #BDB5A8;border-radius:6px;background:#fff;color:var(--tinta)}
.busca:focus-visible{outline:3px solid var(--fio);outline-offset:1px}
.chips{display:flex;gap:8px;overflow-x:auto;padding-top:8px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.chips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:.86rem;font-weight:600;border:1px solid #BDB5A8;background:var(--cartao);color:var(--graf);border-radius:999px;padding:7px 12px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--graf);border-color:var(--graf);color:#fff}
.chip:focus-visible{outline:3px solid var(--fio);outline-offset:1px}
.chip span{font-weight:400;opacity:.75}
.contagem{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:.82rem;color:var(--cinza);margin:6px 0 10px}
.grade{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media (min-width:640px){.grade{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
@media (min-width:900px){.grade{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (min-width:1140px){.grade{grid-template-columns:repeat(5,minmax(0,1fr))}}
.card{background:var(--cartao);border:1px solid var(--linha);border-radius:8px;overflow:hidden;display:flex;flex-direction:column;position:relative}
.card[hidden]{display:none}
.foto{display:block;background:#fff;aspect-ratio:1/1}
.foto img{display:block;width:100%;height:100%;object-fit:contain}
.tag{position:absolute;top:8px;left:8px;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:.7rem;font-weight:700;letter-spacing:.02em;background:var(--fio);color:#fff;border-radius:3px;padding:2px 6px}
.corpo{padding:9px 10px 10px;display:flex;flex-direction:column;flex:1}
.card h2{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:.9rem;font-weight:650;line-height:1.3;margin:0 0 4px;color:var(--graf);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.preco{font-size:.8rem;color:var(--cinza);margin:0 0 9px;flex:1}
a.botao{display:block;text-align:center;text-decoration:none;font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-weight:700;font-size:.86rem;line-height:1.25;color:#fff;background:var(--fio);border-radius:5px;padding:10px 6px}
a.botao:hover,a.botao:focus-visible{background:var(--fio-escuro)}
a.botao:focus-visible{outline:3px solid var(--graf);outline-offset:2px}
.vazio{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--cinza);padding:24px 0;text-align:center}
footer{margin-top:28px;font-size:.88rem;color:var(--cinza);border-top:1px solid #CFC8BC;padding-top:14px;max-width:720px}
footer p{margin:0 0 8px}
footer a{color:var(--fio-escuro)}
.recente{margin:0 0 14px}
.recente h2.titulo{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;font-size:1rem;font-weight:800;color:var(--graf);margin:0 0 8px}
.recente .grade{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
"""

# Contador (ver docstring). `__NS__` é trocado pelo namespace na geração. O clique NÃO tem preventDefault: o link segue
# sozinho; o fetch keepalive sobrevive à troca de página e, se o contador cair, só se perde a contagem.
# Origem (12/10, córtex): ?o=pin|ig|tt na URL da página; sem parâmetro = tt (a bio do TikTok de hoje); outro valor =
# "outro" (não cria chave nova por erro de digitação). Chaves: a da página (P: "visita" no index, "pv-<MLB>" na página
# do produto) e P-<o>; no clique, c-<código> e clique-<o>.
JS_CONTADOR = """
(function(){
  var B='__BASE__', N='__NS__', P='__PAG__';
  var m=/[?&]o=([a-z]+)/.exec(location.search), o=m?m[1]:'tt';
  if(['pin','ig','tt'].indexOf(o)<0){o='outro';}
  function hit(k){try{fetch(B+'/hit/'+N+'/'+k,{keepalive:true,credentials:'omit',cache:'no-store',referrerPolicy:'no-referrer'}).catch(function(){});}catch(e){}}
  hit(P);
  hit(P+'-'+o);
  document.addEventListener('click',function(ev){
    var a=ev.target&&ev.target.closest?ev.target.closest('a[data-cod]'):null;
    if(!a){return;}
    hit('c-'+a.getAttribute('data-cod'));
    hit('clique-'+o);
  },true);
})();
"""
ORIGENS = ("tt", "pin", "ig", "outro")


def js_contador(ns: str, pagina: str) -> str:
    return JS_CONTADOR.replace("__BASE__", CONTADOR).replace("__NS__", ns).replace("__PAG__", pagina)


# ───────────── Pinterest por RSS (12/10, item vitrine-rss-pinterest-12out) ─────────────
# help.pinterest.com/en/business/article/auto-publish-pins-from-your-rss-feed: o link de cada item tem de estar no
# NOSSO domínio (reivindicado) e o pin é de imagem. Layout igual ao da rotina do Managed Agents
# (agrodoc tools/gerenciados/canal-afiliado-diario.system.md): p/<MLB>.html, m/<MLB>.png, feed.xml, publicados.json.
# Só entra produto com conteúdo REFUTADO (item de afiliado da esteira postado ou com render pronto, cujo roteiro passou
# no refutador) e que está na página. No feed, só os já POSTADOS com capa nossa: volume de afiliado é spam pela regra
# do Pinterest, e assim o feed cresce no passo da esteira (≈ 1 por dia), não 85 de uma vez.
SITE = "https://marcello00921.github.io/puxandoofio-links/"
# Código da meta p:domain_verify do Pinterest: vem do Marcello (só ele loga na conta). Vazio = a meta não sai.
PINTEREST_VERIFICACAO = ""
ESTADOS_REFUTADOS = ("postado", "render_ok")
FEED_MAX = 50
AVISO_IA = "Feito com ajuda de IA."
_FRASE_FORA = re.compile(r"(?i)\blink\b|\bbio\b|R\$|\bpre[çc]o\b|\bcomiss")


def mlb_arquivo(mlb: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(mlb).upper())


def frases_do_roteiro(texto: str, n: int = 2) -> list:
    """1–2 frases tiradas LITERALMENTE do roteiro refutado (sem a que fala de link/bio/preço/comissão)."""
    frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", str(texto or "").strip()) if f.strip()]
    return [f for f in frases if not _FRASE_FORA.search(f)][:n]


def refutados(itens, agrodoc: Path = AGRODOC) -> list:
    """[{cod, mlb, arq, titulo, foto, frases, tema, peca, estado, postado, capa}] dos itens de afiliado da esteira com
    roteiro refutado e produto na página; mais recente primeiro (postados antes, pela hora do post)."""
    try:
        fila = json.loads((agrodoc / "dados" / "esteira" / "fila.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    its = fila.get("itens", fila) if isinstance(fila, dict) else fila
    its = its if isinstance(its, list) else list(its.values()) if isinstance(its, dict) else []
    por_cod = {i["cod"]: i for i in itens}
    postados = {r["tema"]: r["postado"] for r in recentes(itens, agrodoc, n=10 ** 6)}
    out, vistos = [], set()
    for it in its:
        if not isinstance(it, dict) or it.get("tipo") != "afiliado" or it.get("estado") not in ESTADOS_REFUTADOS:
            continue
        cod = _cod(it.get("link_ml"))
        if cod not in por_cod or cod in vistos:
            continue
        frases = frases_do_roteiro(it.get("texto"))
        if not frases:
            continue
        vistos.add(cod)
        p = por_cod[cod]
        peca = str(it.get("peca") or "").replace("corte_", "")
        capa = agrodoc / "saida" / "diretor" / str(it.get("tema")) / f"capa_af_{peca}.png"
        postado = postados.get(it.get("tema")) if it.get("estado") == "postado" else None
        # a capa (m/<MLB>.png, ~0,8 MB) só sobe com o vídeo no ar: antes disso a página usa a foto do anúncio
        out.append({"cod": cod, "mlb": p["mlb"], "arq": mlb_arquivo(p["mlb"]), "titulo": p["titulo"], "foto": p["foto"],
                    "frases": frases, "tema": it.get("tema"), "peca": it.get("peca"), "estado": it.get("estado"),
                    "postado": postado, "capa": capa if (postado and capa.is_file()) else None})
    out.sort(key=lambda r: r["postado"] or "", reverse=True)
    return out


def pagina_produto(r, ns=NS) -> str:
    e = html.escape
    href = f"https://meli.la/{r['cod']}"
    texto = "".join(f"<p>{e(f)}</p>" for f in r["frases"])
    foto_ml = (f'<a class="foto" href="{href}" data-cod="{e(r["cod"])}" rel="{REL}" tabindex="-1" aria-hidden="true">'
               f'<img src="{e(r["foto"])}" width="320" height="320" decoding="async" alt="{e(r["titulo"])}"></a>')
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="{REFERRER}">
<meta name="robots" content="noindex">
<title>{e(r['titulo'])} · Puxando o Fio</title>
<meta property="og:image" content="{e(SITE + 'm/' + r['arq'] + '.png') if r.get('capa') else e(r['foto'])}">
<style>{CSS}
.produto{{max-width:560px}}.produto .foto{{max-width:320px}}.produto p{{margin:0 0 10px}}</style>
</head>
<body>
<main class="produto">
  <header>
    <h1>{e(r['titulo'])}</h1>
    <p><a href="../">Puxando o Fio · todos os produtos</a></p>
  </header>
  <p class="aviso"><strong>#publi</strong> · Link de afiliado: o canal ganha comissão se você comprar, sem custo a mais para você. {AVISO_IA}</p>
  {foto_ml}
  <div class="corpo">{texto}<p class="preco">Ver preço no Mercado Livre</p>
  <a class="botao" href="{href}" data-cod="{e(r['cod'])}" rel="{REL}">Ver no Mercado Livre</a></div>
  <footer><p>Foto do anúncio no Mercado Livre. O texto vem do roteiro do nosso vídeo. Sem cookies e sem dado pessoal: a página só soma visitas e cliques num contador público (Abacus).</p></footer>
</main>
<script>{js_contador(ns, "pv-" + r['arq'])}</script>
</body>
</html>
"""


def _rfc822(iso: str) -> str:
    t = dt.datetime.fromisoformat(iso)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone(dt.timedelta(hours=-4)))      # hora do log da esteira: local (UTC-4)
    return t.strftime("%a, %d %b %Y %H:%M:%S %z")


def item_feed(r, tamanho: int) -> str:
    e = html.escape
    desc = " ".join(r["frases"]) + " #publi · link de afiliado. " + AVISO_IA
    return (f"<item><title>{e(r['titulo'])}</title><description>{e(desc)}</description>"
            f"<link>{SITE}p/{r['arq']}.html?o=pin</link>"
            f'<guid isPermaLink="false">puxandoofio-{r["arq"]}</guid><pubDate>{_rfc822(r["postado"])}</pubDate>'
            f'<enclosure url="{SITE}m/{r["arq"]}.png" type="image/png" length="{tamanho}"/></item>')


def feed_xml(itens_xml: list) -> str:
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>Puxando o Fio · vitrine</title><link>{SITE}</link>"
            "<description>Os produtos dos vídeos do Puxando o Fio, com o link de cada um no Mercado Livre.</description>"
            "<language>pt-BR</language>\n" + "\n".join(itens_xml[:FEED_MAX]) + "\n</channel></rss>\n")


def escrever_pinterest(itens, pasta: Path = AQUI, agrodoc: Path = AGRODOC, ns=NS) -> dict:
    """Escreve p/, m/, feed.xml e publicados.json. Preserva o que a rotina do Managed Agents já publicou (itens do
    feed e entradas de publicados.json de MLB que este gerador não conhece). Devolve o resumo."""
    import shutil
    refs = refutados(itens, agrodoc)
    (pasta / "p").mkdir(exist_ok=True)
    (pasta / "m").mkdir(exist_ok=True)
    for r in refs:
        (pasta / "p" / f"{r['arq']}.html").write_text(pagina_produto(r, ns), encoding="utf-8", newline="\n")
        if r["capa"]:
            alvo = pasta / "m" / f"{r['arq']}.png"
            if not alvo.is_file() or alvo.read_bytes() != r["capa"].read_bytes():
                shutil.copyfile(r["capa"], alvo)
    no_feed = [r for r in refs if r["postado"] and r["capa"]]
    nossos = {r["arq"] for r in no_feed}
    antigo_feed = (pasta / "feed.xml").read_text(encoding="utf-8") if (pasta / "feed.xml").is_file() else ""
    alheios = [b for b in re.findall(r"<item>.*?</item>", antigo_feed, re.S)
               if re.search(r"puxandoofio-([A-Z0-9]+)</guid>", b) and
               re.search(r"puxandoofio-([A-Z0-9]+)</guid>", b).group(1) not in nossos]
    itens_xml = [(r["postado"], item_feed(r, (pasta / "m" / f"{r['arq']}.png").stat().st_size)) for r in no_feed]
    for b in alheios:
        m = re.search(r"<pubDate>(.*?)</pubDate>", b)
        try:
            quando = dt.datetime.strptime(m.group(1), "%a, %d %b %Y %H:%M:%S %z").isoformat() if m else ""
        except ValueError:
            quando = ""
        itens_xml.append((quando, b))
    itens_xml.sort(key=lambda x: x[0], reverse=True)
    (pasta / "feed.xml").write_text(feed_xml([x[1] for x in itens_xml]), encoding="utf-8", newline="\n")
    try:
        pub = json.loads((pasta / "publicados.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pub = []
    pub = [x for x in pub if x.get("mlb") not in nossos]
    pub += [{"data": r["postado"][:10], "mlb": r["arq"], "titulo": r["titulo"], "pagina": f"p/{r['arq']}.html",
             "origem_texto": "roteiro_refutado"} for r in no_feed]
    pub.sort(key=lambda x: (x.get("data") or "", x.get("mlb") or ""))
    (pasta / "publicados.json").write_text(json.dumps(pub, ensure_ascii=False, indent=1) + "\n", encoding="utf-8",
                                           newline="\n")
    return {"paginas": len(refs), "no_feed": len(no_feed), "alheios": len(alheios),
            "sem_capa": [r["arq"] for r in refs if not r["capa"]]}
# Referrer (12/10, córtex): o no-referrer de 08/10 (9e46dec, sem razão escrita no commit nem no gerador) escondia do ML
# a origem do clique, e o ML só paga "os meios informados no registro". Agora strict-origin-when-cross-origin: o ML vê
# a origem (marcello00921.github.io), sem o caminho. O fetch do contador segue sem referrer (não precisa).
REFERRER = "strict-origin-when-cross-origin"
REL = "sponsored noopener"          # sem "noreferrer": ele também apagava o referrer no clique

JS = """
(function(){
  var sem=function(s){return s.normalize('NFD').replace(/[\\u0300-\\u036f]/g,'').toLowerCase().trim();};
  var cards=[].slice.call(document.querySelectorAll('#grade .card'));
  var chips=[].slice.call(document.querySelectorAll('.chip'));
  var busca=document.getElementById('busca');
  var cont=document.getElementById('contagem');
  var vazio=document.getElementById('vazio');
  var cat='todos';
  function aplicar(){
    var q=sem(busca.value), n=0;
    cards.forEach(function(c){
      var ok=(cat==='todos'||(' '+c.getAttribute('data-cat')+' ').indexOf(' '+cat+' ')>=0)&&(!q||c.getAttribute('data-q').indexOf(q)>=0);
      c.hidden=!ok; if(ok){n++;}
    });
    cont.textContent=n+(n===1?' produto':' produtos');
    vazio.hidden=n>0;
  }
  function escolher(novo){
    cat=novo;
    chips.forEach(function(b){b.setAttribute('aria-pressed',b.getAttribute('data-cat')===cat?'true':'false');});
    aplicar();
  }
  chips.forEach(function(b){b.addEventListener('click',function(){escolher(b.getAttribute('data-cat'));});});
  busca.addEventListener('input',aplicar);
  var h=decodeURIComponent((location.hash||'').slice(1));
  if(h&&chips.some(function(b){return b.getAttribute('data-cat')===h;})){escolher(h);}else{aplicar();}
})();
"""


def _card(i, n, e=html.escape):
    href = f"https://meli.la/{i['cod']}"
    cats = i["cat"] + (" videos" if i["video"] else "")
    q = sem_acento(i["titulo"] + " " + CATS[i["cat"]])
    carga = 'loading="eager" fetchpriority="high"' if n < 4 else 'loading="lazy"'
    tag = '<span class="tag">Do vídeo</span>' if i["video"] else ""
    cod = e(i["cod"])
    return (f'<li class="card" data-cat="{cats}" data-q="{e(q)}" data-mlb="{e(i["mlb"])}">'
            f'<a class="foto" href="{href}" data-cod="{cod}" rel="{REL}" tabindex="-1" aria-hidden="true">'
            f'<img src="{e(i["foto"])}" width="320" height="320" {carga} decoding="async" alt="{e(i["titulo"])}"></a>{tag}'
            f'<div class="corpo"><h2>{e(i["titulo"])}</h2><p class="preco">Ver preço no Mercado Livre</p>'
            f'<a class="botao" href="{href}" data-cod="{cod}" rel="{REL}">Ver no Mercado Livre</a></div></li>')


def _bloco_recente(itens, rec) -> str:
    por_cod = {i["cod"]: i for i in itens}
    cards = [_card(por_cod[r["cod"]], 0) for r in rec or [] if r["cod"] in por_cod]
    if not cards:
        return ""
    return ('  <section class="recente" aria-labelledby="t-recente">\n'
            '    <h2 class="titulo" id="t-recente">Do vídeo mais recente</h2>\n'
            f'    <ul class="grade">{"".join(cards)}</ul>\n  </section>\n')


def gerar(itens, ns=NS, rec=None):
    e = html.escape
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", ns):
        raise ValueError(f"namespace fora do formato do Abacus: {ns}")
    contagem = {k: 0 for k in CATS}
    for i in itens:
        contagem[i["cat"]] += 1
    n_video = sum(1 for i in itens if i["video"])
    chips = [f'<button type="button" class="chip" data-cat="todos" aria-pressed="true">Todos <span>{len(itens)}</span></button>',
             f'<button type="button" class="chip" data-cat="videos" aria-pressed="false">Dos vídeos <span>{n_video}</span></button>']
    for k, rot in CATS.items():
        if contagem[k]:
            chips.append(f'<button type="button" class="chip" data-cat="{k}" aria-pressed="false">{e(rot)} <span>{contagem[k]}</span></button>')
    cards = [_card(i, n) for n, i in enumerate(itens)]
    bloco = _bloco_recente(itens, rec)
    contador = js_contador(ns, "visita")
    verif = (f'<meta name="p:domain_verify" content="{e(PINTEREST_VERIFICACAO)}">\n' if PINTEREST_VERIFICACAO else "")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="{REFERRER}">
<meta name="robots" content="noindex">
<title>Puxando o Fio · produtos no Mercado Livre</title>
<meta name="description" content="Os produtos dos vídeos do Puxando o Fio e outros achados, com o link de cada um no Mercado Livre.">
{verif}<link rel="preconnect" href="https://http2.mlstatic.com">
<script>document.documentElement.className+=' js';</script>
<style>{CSS}</style>
</head>
<body>
<main>
  <header>
    <h1>Puxando o Fio</h1>
    <p>Os produtos dos nossos vídeos e outros achados, com o link de cada um no Mercado Livre.</p>
  </header>
  <p class="aviso"><strong>#publi</strong> · Links de afiliado: podemos receber comissão pelas compras. Os vídeos do canal têm narração com voz sintética (IA).</p>
{bloco}  <div class="barra">
    <input id="busca" class="busca" type="search" placeholder="Buscar produto" aria-label="Buscar produto" autocomplete="off">
    <div class="chips" role="group" aria-label="Categorias">{''.join(chips)}</div>
  </div>
  <p id="contagem" class="contagem" aria-live="polite">{len(itens)} produtos</p>
  <ul class="grade" id="grade">
{chr(10).join(cards)}
  </ul>
  <p id="vazio" class="vazio" hidden>Nenhum produto com esse nome. Tente outra palavra ou outra categoria.</p>
  <footer>
    <p><strong>Quem mantém esta página:</strong> Puxando o Fio, canal de vídeos que explica como as coisas funcionam por dentro. Contato: <a href="https://www.tiktok.com/@puxandoofioo" rel="noopener">@puxandoofioo no TikTok</a>.</p>
    <p>Esta página não vende nem entrega nada. A venda é feita no Mercado Livre: preço, frete, estoque, troca, devolução e garantia são os do anúncio no dia da compra. As fotos vêm dos próprios anúncios; os nomes foram resumidos.</p>
    <p>Sem cookies e sem dado pessoal: a página só soma quantas visitas e quantos cliques cada produto recebe, num contador público (Abacus).</p>
  </footer>
</main>
<script>{JS}</script>
<script>{contador}</script>
</body>
</html>
"""


def main():
    itens, fora, erros = montar_itens()
    for x in erros:
        print("ERRO:", x)
    print(f"{len(itens)} produtos na página ({sum(i['video'] for i in itens)} dos vídeos); fora: {fora}")
    if erros:
        return 1
    if "--conferir" in sys.argv:
        return 0
    rec = recentes(itens)
    print("do vídeo mais recente:", ", ".join(f"{r['cod']} ({r['tema']}, {r['postado'][:16]})" for r in rec)
          or "nenhum post de afiliado achado (bloco fora)")
    (AQUI / "index.html").write_text(gerar(itens, NS, rec), encoding="utf-8", newline="\n")
    print("index.html gravado:", (AQUI / "index.html").stat().st_size, "bytes")
    pin = escrever_pinterest(itens)
    print(f"Pinterest: {pin['paginas']} páginas p/, {pin['no_feed']} no feed.xml (postados com capa), "
          f"{pin['alheios']} itens da rotina preservados; sem capa: {pin['sem_capa']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
