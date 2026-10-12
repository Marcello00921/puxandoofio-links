"""Gera index.html (página da bio do Puxando o Fio) a partir de produtos.json + os 8 produtos dos vídeos.

Uso:  python _gerar.py                 -> lê preço, contador e vendidos, grava _estado.json e reescreve index.html
      python _gerar.py --sem-contador  -> idem, sem ler o contador (ficam os cliques do _estado.json anterior)
      python _gerar.py --conferir      -> só confere (rc 1 se faltar título curto, categoria ou link)

produtos.json fica FORA do commit (traz comissão e notas internas; o repo é público). A origem dele é a
coleta da central de afiliados registrada em agrodoc/tools/explicador/afiliado_links.md (09/10/2026).
O prefixo "_" deixa este arquivo, _precos.json e _estado.json fora do site publicado (Jekyll ignora "_*").
_estado.json é a fotografia do que a página mostra além de produtos.json (preço válido, pausados, cliques, vendidos,
hora): gerar() é função dela, então gerar(itens, NS, rec) reproduz o index.html byte a byte (a conferência do
contador compara assim).

Regras da página (pedido do Marcello, 09/10, boost da landing no TikTok; 12/10: "mais comercial pro pessoal que
clicar no tiktok, com preço, oferta imperdível, coisas que tem um CTA forte"). Fontes lidas em 12/10:
agrodoc saida/explicador/vitrine_comercial_12out/fontes_regras.md.
- selo "Publicidade · links de afiliado" no topo, visível sem clique, mais o rótulo de IA do canal (CONAR, guia de
  influenciadores 1.1.1; termos do ML Afiliados 5.1);
- preço só o lido na API oficial do ML (agrodoc tools/explicador/vitrine_precos.py), com a hora da leitura no cartão
  ("preço de DD/MM, HHh · pode mudar"). Com mais de 24 h, o gerador não mostra e o JS da página esconde (a página
  pode ficar no ar sem o gerador rodar). Sem leitura válida, o cartão diz "preço e frete atualizados no Mercado
  Livre" (termos 5.4: só o que o anúncio diz; CDC arts. 30 e 37);
- preço riscado e "% OFF" só com o preço anterior do próprio ML; SELO_OFERTA só em desconto do ML ≥ SELO_OFERTA_MIN;
  parcela não aparece (a API de item não dá, e o Decreto 5.903 art. 3º pede total, número e valor);
- anúncio pausado, encerrado ou sem estoque na última leitura válida sai da página;
- meli.la exatamente como o ML gerou, sem parâmetro (termos 1.8); o botão diz que o destino é o Mercado Livre, sem
  logotipo nem cara de loja do ML;
- foto real do anúncio (mlstatic), sem editar; sem cookie, sem pop-up, sem script de terceiro;
- ordem da grade: mais clicados (contador) no topo; depois os dos vídeos, o maior desconto do ML e os mais vendidos
  ("+N vendidos" da coleta da central: número que o próprio anúncio mostra e que só cresce).

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
ESTADO = AQUI / "_estado.json"
BRT = dt.timezone(dt.timedelta(hours=-3))
# "Oferta imperdível" (palavra do Marcello, 12/10) só em desconto do PRÓPRIO ML a partir deste %. None desliga: os
# termos do ML Afiliados (5.4) limitam o post ao que o anúncio diz, e o selo é adjetivo nosso sobre esse desconto.
SELO_OFERTA, SELO_OFERTA_MIN = "Oferta imperdível", 20

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
        itens.append({"cod": cod, "titulo": titulo, "cat": cat, "video": cod in COM_POST, "mlb": mlb, "foto": foto_320(foto),
                      "foto_grande": foto})
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
        itens.append({"cod": cod, "titulo": titulo, "cat": cat, "video": False, "mlb": p["mlb"], "foto": foto_320(p["foto"]),
                      "foto_grande": p["foto"]})
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


# 12/10 · contraste (WCAG AA, texto ≥ 4,5:1): branco sobre --cta 5,9:1, sobre --fio 7,9:1; --verde 5,4:1 e --cinza
# 7,0:1 sobre branco. Botão ≥ 52 px de altura (o portão do agrodoc cobra ≥ 48 px a 375 px).
CSS = """
:root{--papel:#F4F1EA;--cartao:#fff;--tinta:#1F1D1A;--graf:#2E2B27;--cinza:#5F584F;--linha:#DDD6CA;--fio:#A3121E;--cta:#C8102E;--cta-escuro:#8E0A1F;--verde:#0A7A3D}
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--papel);color:var(--tinta);font-family:system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;line-height:1.4;-webkit-text-size-adjust:100%}
.publi{margin:0;background:var(--tinta);color:#fff;font-size:.8rem;line-height:1.35;padding:8px 16px;text-align:center}
.publi strong{color:#FFD9A8}
main{max-width:1180px;margin:0 auto;padding:14px 16px 40px}
header{border-left:4px solid var(--fio);padding-left:12px;margin-bottom:16px}
h1{font-size:1.35rem;font-weight:800;letter-spacing:-.01em;margin:0;color:var(--graf);line-height:1.2}
header p{margin:2px 0 0;color:var(--cinza);font-size:.92rem}
header .ia{font-size:.78rem}
h2.titulo{font-size:1.1rem;font-weight:800;color:var(--graf);margin:0 0 10px}
.sub{margin:-6px 0 10px;font-size:.78rem;color:var(--cinza)}
.recente,.ofertas{margin:0 0 22px}
.destaque{background:var(--cartao);border:2px solid var(--cta);border-radius:12px;overflow:hidden;margin:0 0 12px;position:relative}
.destaque .foto{display:block;background:#fff;height:230px}
.destaque .foto img{display:block;width:100%;height:100%;object-fit:contain}
.destaque .corpo{padding:10px 12px 12px}
.destaque h3{font-size:1.15rem;line-height:1.25}
.selo-video{align-self:flex-start;margin:0 0 6px;background:var(--fio);color:#fff;font-size:.75rem;font-weight:800;letter-spacing:.03em;text-transform:uppercase;border-radius:4px;padding:3px 8px}
@media (min-width:640px){.destaque{display:grid;grid-template-columns:320px 1fr}.destaque .foto{height:320px}.destaque .corpo{padding:18px}}
.trilho{list-style:none;margin:0;padding:0 0 6px;display:grid;grid-auto-flow:column;grid-auto-columns:minmax(150px,46%);gap:10px;overflow-x:auto;scroll-snap-type:x proximity}
@media (min-width:640px){.trilho{grid-auto-columns:210px}}
.card,.mini{background:var(--cartao);border:1px solid var(--linha);border-radius:10px;overflow:hidden;display:flex;flex-direction:column;position:relative}
.mini{scroll-snap-align:start}
.card[hidden],.ofertas[hidden]{display:none}
.card .foto,.mini .foto{display:block;background:#fff;aspect-ratio:1/1}
.card .foto img,.mini .foto img{display:block;width:100%;height:100%;object-fit:contain}
.tags{position:absolute;top:8px;left:8px;display:flex;flex-direction:column;align-items:flex-start;gap:4px}
.tag{font-size:.7rem;font-weight:800;letter-spacing:.02em;background:var(--fio);color:#fff;border-radius:4px;padding:2px 7px}
.tag.quente{background:var(--cta)}
.corpo{padding:9px 10px 10px;display:flex;flex-direction:column;flex:1}
h3{font-size:.92rem;font-weight:700;line-height:1.3;margin:0 0 6px;color:var(--graf);display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
.oferta{margin:0 0 6px}
.preco{margin:0;font-size:1.35rem;font-weight:800;line-height:1.15;letter-spacing:-.01em;color:var(--tinta)}
.antes{margin:2px 0 0;font-size:.82rem;color:#6B645A}
.off{color:var(--verde);font-weight:800;margin-left:6px}
.frete{margin:2px 0 0;font-size:.82rem;font-weight:700;color:var(--verde)}
.quando{margin:3px 0 0;font-size:.75rem;color:var(--cinza)}
.neutro{margin:0 0 6px;font-size:.86rem;color:var(--cinza)}
.oferta+.neutro,.expirou .oferta,.expirou .tag.quente{display:none}
.expirou .oferta+.neutro{display:block}
.vendidos{margin:0 0 8px;font-size:.8rem;color:var(--cinza)}
a.botao{margin-top:auto;display:flex;flex-direction:column;justify-content:center;align-items:center;min-height:52px;text-align:center;text-decoration:none;font-weight:800;font-size:1rem;line-height:1.15;color:#fff;background:var(--cta);border-radius:8px;padding:8px 6px;box-shadow:0 2px 0 var(--cta-escuro)}
a.botao span{font-weight:600;font-size:.78rem}
a.botao:hover,a.botao:focus-visible{background:var(--cta-escuro)}
a.botao:focus-visible{outline:3px solid var(--graf);outline-offset:2px}
.destaque a.botao{min-height:56px;font-size:1.1rem}
.barra{display:none;position:sticky;top:0;z-index:2;background:var(--papel);padding:8px 16px 10px;margin:0 -16px 6px;border-bottom:1px solid var(--linha)}
.js .barra{display:block}
.busca{width:100%;font:inherit;font-size:1rem;padding:11px 12px;border:1px solid #A8A092;border-radius:8px;background:#fff;color:var(--tinta)}
.busca:focus-visible{outline:3px solid var(--fio);outline-offset:1px}
.chips{display:flex;gap:8px;overflow-x:auto;padding-top:8px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.chips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;font:inherit;font-size:.86rem;font-weight:650;border:1px solid #A8A092;background:var(--cartao);color:var(--graf);border-radius:999px;padding:8px 13px;cursor:pointer}
.chip[aria-pressed="true"]{background:var(--graf);border-color:var(--graf);color:#fff}
.chip:focus-visible{outline:3px solid var(--fio);outline-offset:1px}
.chip span{font-weight:400}
.contagem{font-size:.82rem;color:var(--cinza);margin:6px 0 10px}
.grade{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
@media (min-width:640px){.grade{grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}
@media (min-width:900px){.grade{grid-template-columns:repeat(4,minmax(0,1fr))}}
@media (min-width:1140px){.grade{grid-template-columns:repeat(5,minmax(0,1fr))}}
.vazio{color:var(--cinza);padding:24px 0;text-align:center}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap}
footer{margin-top:28px;font-size:.88rem;color:var(--cinza);border-top:1px solid #CFC8BC;padding-top:14px;max-width:720px}
footer p{margin:0 0 8px}
footer a{color:#5E0810}
.aviso{font-size:.86rem;background:var(--cartao);border:1px solid var(--linha);border-radius:6px;padding:9px 12px;margin:0 0 12px;color:var(--graf)}
.aviso strong{color:var(--fio)}
.produto .foto{display:block;background:#fff;aspect-ratio:1/1}
.produto .foto img{display:block;width:100%;height:100%;object-fit:contain}
.produto .preco{font-size:.86rem;font-weight:400;color:var(--cinza)}
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
  // preço com mais de 24 h some: a página pode ficar no ar sem o gerador rodar (regra no docstring)
  var LIM=864e5, agora=Date.now();
  [].forEach.call(document.querySelectorAll('[data-em]'),function(p){
    if(!(agora-Date.parse(p.getAttribute('data-em'))<LIM)){var c=p.closest('[data-cod]');if(c){c.className+=' expirou';}}
  });
  [].forEach.call(document.querySelectorAll('.ofertas'),function(s){if(!s.querySelector('.mini:not(.expirou)')){s.hidden=true;}});
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


def _mlb(i) -> str:
    return i["mlb"].replace("-", "").upper()


def reais(v: float) -> str:
    """1299.9 -> 'R$ 1.299,90'; 1299.0 -> 'R$ 1.299' (centavo só quando há, como o ML mostra)."""
    inteiro, cent = divmod(round(v * 100), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + (f",{cent:02d}" if cent else "")


def vendidos_txt(n: int) -> str:
    return f"+{n // 1000} mil vendidos" if n >= 10000 else f"+{n:,} vendidos".replace(",", ".")


def ler_estado() -> dict:
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def montar_estado(itens, ler_contador=True, anterior=None) -> dict:
    """Fotografia do que a página mostra além de produtos.json (vira _estado.json). Fonte que falta (sem agrodoc ao
    lado, sem token do ML, contador fora) deixa o campo vazio: a página cai no texto neutro, nunca em número chutado."""
    anterior = anterior or {}
    agora = dt.datetime.now(BRT)
    est = {"gerado_em": agora.isoformat(timespec="seconds"), "precos": {}, "fora": {}, "cliques": {},
           "cliques_lido_em": None, "vendidos": {}, "vendidos_de": None}
    cod_de = {_mlb(i): i["cod"] for i in itens}
    sys.path.insert(0, str(AGRODOC / "tools" / "explicador"))
    try:
        try:
            import vitrine_precos as vp  # validade e "sai da vitrine": uma regra só, a do leitor de preço
            for m, r in (vp.carregar().get("itens") or {}).items():
                c = cod_de.get(m)
                if c and vp.vale(r, agora):
                    razao = vp.fora_da_vitrine(r)
                    if razao:
                        est["fora"][c] = razao
                    else:
                        est["precos"][c] = r
        except ImportError:
            pass
        if ler_contador:
            try:
                import vitrine_contador as vc
                lido = vc.ler()
                if lido.get("cliques") is not None:
                    est["cliques"], est["cliques_lido_em"] = lido["por_produto"], lido["lido_em"]
                else:
                    print("contador:", lido.get("motivo"))
            except ImportError:
                pass
    finally:
        sys.path.pop(0)
    if not est["cliques_lido_em"]:
        est["cliques"], est["cliques_lido_em"] = anterior.get("cliques") or {}, anterior.get("cliques_lido_em")
    try:
        for linha in (AGRODOC / "tools" / "explicador" / "afiliado_ml_produtos.jsonl").read_text(encoding="utf-8").splitlines():
            j = json.loads(linha)
            c = cod_de.get(str(j.get("id", "")).replace("-", "").upper())
            if c and j.get("vendidos_min"):
                est["vendidos"][c] = int(j["vendidos_min"])
                est["vendidos_de"] = max(est["vendidos_de"] or "", str(j.get("coletado") or "")[:10]) or None
    except (OSError, ValueError):
        pass
    return est


def ordenar(itens, est, videos) -> list:
    """Grade: mais clicados no topo; depois os dos vídeos, o maior desconto do ML e os mais vendidos. Empate fica na
    ordem de montar_itens (estável e sem acaso: a conferência do contador compara o HTML byte a byte)."""
    cl, pr, ve = est.get("cliques") or {}, est.get("precos") or {}, est.get("vendidos") or {}

    def chave(par):
        n, i = par
        c = i["cod"]
        return -cl.get(c, 0), c not in videos, -((pr.get(c) or {}).get("desconto_pct") or 0), -ve.get(c, 0), n
    return [i for _n, i in sorted(enumerate(itens), key=chave)]


def _preco(cod, est, e=html.escape) -> str:
    """Preço lido na API (com a hora) ou o texto neutro. O neutro vai sempre junto: o CSS o mostra quando o JS da
    página expira o preço (mais de 24 h)."""
    neutro = '<p class="neutro">Preço e frete atualizados no Mercado Livre</p>'
    r = (est.get("precos") or {}).get(cod)
    if not r:
        return neutro
    lido = dt.datetime.fromisoformat(r["lido_em"]).astimezone(BRT)
    out = [f'<div class="oferta"><p class="preco" data-preco="{r["preco"]}" data-em="{e(r["lido_em"])}">'
           f'<span class="sr">Preço: </span>{reais(r["preco"])}</p>']
    if r.get("preco_antes") and r.get("desconto_pct"):
        out.append(f'<p class="antes"><s data-antes="{r["preco_antes"]}"><span class="sr">Preço anterior: </span>'
                   f'{reais(r["preco_antes"])}</s><span class="off" data-off="{r["desconto_pct"]}">'
                   f'{r["desconto_pct"]}% OFF</span></p>')
    if r.get("frete_gratis") is True:
        out.append('<p class="frete">Frete grátis</p>')
    out.append(f'<p class="quando">Preço de {lido:%d/%m}, {lido.hour}h · pode mudar</p></div>{neutro}')
    return "".join(out)


def _tags(i, est, videos) -> str:
    """videos vazio = sem a etiqueta "Do vídeo" (no bloco "Produtos dos vídeos" ela só repetiria o título)."""
    t = ['<span class="tag">Do vídeo</span>'] if i["cod"] in videos else []
    r = (est.get("precos") or {}).get(i["cod"])
    if SELO_OFERTA and r and (r.get("desconto_pct") or 0) >= SELO_OFERTA_MIN:
        t.append(f'<span class="tag quente">{html.escape(SELO_OFERTA)}</span>')
    return f'<div class="tags">{"".join(t)}</div>' if t else ""


def _vendidos(cod, est) -> str:
    n = (est.get("vendidos") or {}).get(cod)
    return f'<p class="vendidos">{vendidos_txt(n)}</p>' if n else ""


def _cta(href, cod) -> str:
    return f'<a class="botao" href="{href}" data-cod="{cod}" rel="{REL}">Ver oferta <span>no Mercado Livre</span></a>'


def _foto(href, cod, src, titulo, lado=320, carga='loading="lazy"', e=html.escape) -> str:
    return (f'<a class="foto" href="{href}" data-cod="{cod}" rel="{REL}" tabindex="-1" aria-hidden="true">'
            f'<img src="{e(src)}" width="{lado}" height="{lado}" {carga} decoding="async" alt="{e(titulo)}"></a>')


def _card(i, est, videos, cliques, e=html.escape) -> str:
    href, cod = f"https://meli.la/{i['cod']}", e(i["cod"])
    cats = i["cat"] + (" videos" if i["cod"] in videos else "") + (" mais" if cliques.get(i["cod"]) else "")
    q = sem_acento(i["titulo"] + " " + CATS[i["cat"]])
    return (f'<li class="card" data-cat="{cats}" data-q="{e(q)}" data-mlb="{_mlb(i)}" data-cod="{cod}">'
            f'{_foto(href, cod, i["foto"], i["titulo"])}{_tags(i, est, videos)}'
            f'<div class="corpo"><h3>{e(i["titulo"])}</h3>{_preco(i["cod"], est)}{_vendidos(i["cod"], est)}'
            f'{_cta(href, cod)}</div></li>')


def _mini(i, est, videos, e=html.escape) -> str:
    href, cod = f"https://meli.la/{i['cod']}", e(i["cod"])
    return (f'<li class="mini" data-mlb="{_mlb(i)}" data-cod="{cod}">{_foto(href, cod, i["foto"], i["titulo"])}'
            f'{_tags(i, est, videos)}<div class="corpo"><h3>{e(i["titulo"])}</h3>{_preco(i["cod"], est)}'
            f'{_cta(href, cod)}</div></li>')


def _destaque(i, est, e=html.escape) -> str:
    href, cod = f"https://meli.la/{i['cod']}", e(i["cod"])
    return (f'<article class="destaque" data-mlb="{_mlb(i)}" data-cod="{cod}">'
            f'{_foto(href, cod, i["foto_grande"], i["titulo"], 500, "fetchpriority=" + chr(34) + "high" + chr(34))}'
            f'<div class="corpo"><p class="selo-video">Do vídeo mais recente</p><h3>{e(i["titulo"])}</h3>'
            f'{_preco(i["cod"], est)}{_vendidos(i["cod"], est)}{_cta(href, cod)}</div></article>')


def _bloco_recente(itens, rec, est, videos) -> str:
    """'Produtos dos vídeos': o do post mais recente em destaque; depois os outros com post, o mais novo primeiro
    (os do log da esteira e, na ordem de DOS_VIDEOS, os com post conferido em 09/10). Sem post achado, não há bloco."""
    por_cod = {i["cod"]: i for i in itens}
    ordem = [r["cod"] for r in rec or [] if r["cod"] in por_cod]
    if not ordem:
        return ""
    ordem += [t[0] for t in DOS_VIDEOS if t[0] in COM_POST and t[0] in por_cod and t[0] not in ordem]
    resto = "".join(_mini(por_cod[c], est, set()) for c in ordem[1:])
    return ('  <section class="recente" aria-labelledby="t-recente">\n'
            '    <h2 class="titulo" id="t-recente">Produtos dos vídeos</h2>\n'
            f'    {_destaque(por_cod[ordem[0]], est)}\n'
            + (f'    <ul class="trilho" aria-label="Outros produtos dos vídeos">{resto}</ul>\n' if resto else "")
            + '  </section>\n')


def _bloco_ofertas(itens, est, videos) -> str:
    """Desconto do próprio ML (preço riscado lido na API), o maior primeiro. Sem desconto lido, não há bloco."""
    pr = est.get("precos") or {}
    com = sorted((i for i in itens if (pr.get(i["cod"]) or {}).get("desconto_pct")),
                 key=lambda i: -pr[i["cod"]]["desconto_pct"])[:12]
    if not com:
        return ""
    return ('  <section class="ofertas" aria-labelledby="t-ofertas">\n'
            '    <h2 class="titulo" id="t-ofertas">Em oferta no Mercado Livre</h2>\n'
            '    <p class="sub">Desconto que o próprio Mercado Livre mostra, na hora da leitura do preço.</p>\n'
            f'    <ul class="trilho" aria-label="Produtos em oferta">{"".join(_mini(i, est, videos) for i in com)}</ul>\n'
            '  </section>\n')


def gerar(itens, ns=NS, rec=None, estado=None):
    """index.html. estado=None lê _estado.json (assim gerar(itens, NS, rec) reproduz a página publicada)."""
    e = html.escape
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,64}", ns):
        raise ValueError(f"namespace fora do formato do Abacus: {ns}")
    est = ler_estado() if estado is None else estado
    fora = est.get("fora") or {}
    itens = [i for i in itens if i["cod"] not in fora]
    rec = [r for r in rec or [] if r["cod"] not in fora]
    videos = set(COM_POST) | {r["cod"] for r in rec}
    cliques = est.get("cliques") or {}
    itens = ordenar(itens, est, videos)
    contagem = {k: 0 for k in CATS}
    for i in itens:
        contagem[i["cat"]] += 1
    n_video = sum(1 for i in itens if i["cod"] in videos)
    n_mais = sum(1 for i in itens if cliques.get(i["cod"]))
    chips = [f'<button type="button" class="chip" data-cat="todos" aria-pressed="true">Todos <span>{len(itens)}</span></button>']
    if n_mais:
        chips.append(f'<button type="button" class="chip" data-cat="mais" aria-pressed="false">Mais clicados <span>{n_mais}</span></button>')
    chips.append(f'<button type="button" class="chip" data-cat="videos" aria-pressed="false">Dos vídeos <span>{n_video}</span></button>')
    for k, rot in CATS.items():
        if contagem[k]:
            chips.append(f'<button type="button" class="chip" data-cat="{k}" aria-pressed="false">{e(rot)} <span>{contagem[k]}</span></button>')
    cards = [_card(i, est, videos, cliques) for i in itens]
    bloco = _bloco_recente(itens, rec, est, videos)
    ofertas = _bloco_ofertas(itens, est, videos)
    vendidos_de = est.get("vendidos_de")
    nota_vendidos = (f' "+N vendidos" é o número que o anúncio mostrava em {vendidos_de[8:10]}/{vendidos_de[5:7]} '
                     '(ele só cresce).') if vendidos_de else ""
    contador = js_contador(ns, "visita")
    verif = (f'<meta name="p:domain_verify" content="{e(PINTEREST_VERIFICACAO)}">\n' if PINTEREST_VERIFICACAO else "")
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="{REFERRER}">
<meta name="robots" content="noindex">
<title>Puxando o Fio · produtos dos vídeos no Mercado Livre</title>
<meta name="description" content="Os produtos dos vídeos do Puxando o Fio e outros achados, com o link de cada um no Mercado Livre.">
{verif}<link rel="preconnect" href="https://http2.mlstatic.com">
<script>document.documentElement.className+=' js';</script>
<style>{CSS}</style>
</head>
<body>
<p class="publi" id="publi"><strong>Publicidade · links de afiliado</strong> do Mercado Livre (#publi). Se você comprar por eles, o canal pode ganhar comissão, e o preço para você é o mesmo.</p>
<main>
  <header>
    <h1>Puxando o Fio</h1>
    <p>Os produtos dos nossos vídeos e outros achados, com o link de cada um no Mercado Livre.</p>
    <p class="ia">Os vídeos do canal têm narração com voz sintética (IA).</p>
  </header>
{bloco}{ofertas}  <h2 class="titulo" id="t-todos">Todos os produtos</h2>
  <div class="barra">
    <input id="busca" class="busca" type="search" placeholder="Buscar produto" aria-label="Buscar produto" autocomplete="off">
    <div class="chips" role="group" aria-label="Categorias">{''.join(chips)}</div>
  </div>
  <p id="contagem" class="contagem" aria-live="polite">{len(itens)} produtos</p>
  <ul class="grade" id="grade" aria-labelledby="t-todos">
{chr(10).join(cards)}
  </ul>
  <p id="vazio" class="vazio" hidden>Nenhum produto com esse nome. Tente outra palavra ou outra categoria.</p>
  <footer>
    <p><strong>Quem mantém esta página:</strong> Puxando o Fio, canal de vídeos que explica como as coisas funcionam por dentro. Contato: <a href="https://www.tiktok.com/@puxandoofioo" rel="noopener">@puxandoofioo no TikTok</a>.</p>
    <p>Esta página é do canal, não do Mercado Livre, e não vende nem entrega nada. A venda é feita no Mercado Livre: preço, frete, estoque, troca, devolução e garantia são os do anúncio no momento da compra.</p>
    <p>Preço, preço riscado e "% OFF" só aparecem quando lidos na API oficial do Mercado Livre, com a data e a hora da leitura em cada produto; com mais de 24 horas, somem.{nota_vendidos} As fotos vêm dos próprios anúncios; os nomes foram resumidos.</p>
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
    print(f"{len(itens)} produtos na página ({sum(i['video'] for i in itens)} com post conferido em 09/10); fora: {fora}")
    if erros:
        return 1
    if "--conferir" in sys.argv:
        return 0
    rec = recentes(itens, n=len(itens))
    print("produtos dos vídeos (post mais recente primeiro):",
          ", ".join(f"{r['cod']} ({r['tema']}, {r['postado'][:16]})" for r in rec) or "nenhum post de afiliado achado (bloco fora)")
    est = montar_estado(itens, ler_contador="--sem-contador" not in sys.argv, anterior=ler_estado())
    ESTADO.write_text(json.dumps(est, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8", newline="\n")
    print(f"preço válido {len(est['precos'])} · com desconto do ML "
          f"{sum(1 for r in est['precos'].values() if r.get('desconto_pct'))} · fora (pausado/sem estoque) "
          f"{len(est['fora'])} · cliques {sum(est['cliques'].values())} ({est['cliques_lido_em']}) · "
          f"vendidos {len(est['vendidos'])} ({est['vendidos_de']})")
    (AQUI / "index.html").write_text(gerar(itens, NS, rec, est), encoding="utf-8", newline="\n")
    print("index.html gravado:", (AQUI / "index.html").stat().st_size, "bytes")
    pin = escrever_pinterest(itens)
    print(f"Pinterest: {pin['paginas']} páginas p/, {pin['no_feed']} no feed.xml (postados com capa), "
          f"{pin['alheios']} itens da rotina preservados; sem capa: {pin['sem_capa']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
