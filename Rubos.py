import sys
import os
import subprocess
import ctypes

# ==========================================
# FECHAR O TERMINAL AUTOMATICAMENTE (WINDOWS)
# ==========================================
if os.name == "nt" and "--sem-consola" not in sys.argv:
    pasta_python = os.path.dirname(sys.executable)
    pythonw = os.path.join(pasta_python, "pythonw.exe")
    if os.path.exists(pythonw) and not sys.executable.lower().endswith("pythonw.exe"):
        args_extra = ["--sem-consola"] + [a for a in sys.argv[1:] if a != "--sem-consola"]
        subprocess.Popen(
            [pythonw, os.path.abspath(__file__)] + args_extra,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )
        sys.exit(0)
    else:
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd:
                ctypes.windll.user32.ShowWindow(hwnd, 0)
                ctypes.windll.kernel32.FreeConsole()
        except Exception:
            pass

import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import tkinter.font as tkfont
import requests
import threading
import asyncio
import queue
from datetime import datetime, timedelta
import platform
import json
import re
import ast
import operator
import math
import base64
import io
import time
import wave
import shlex
import difflib
import webbrowser
import urllib.parse
import xml.etree.ElementTree as ET

if os.name == "nt":
    import winreg
    import winsound

# Bibliotecas opcionais (o código funciona mesmo sem elas)
try:
    import speech_recognition as sr
    TEM_SR = True
except ImportError:
    TEM_SR = False

try:
    import sounddevice as sd
    import numpy as np
    TEM_SD = True
except ImportError:
    TEM_SD = False

try:
    import edge_tts
    TEM_EDGE_TTS = True
except ImportError:
    TEM_EDGE_TTS = False

try:
    from PIL import ImageGrab, Image
    TEM_PIL = True
except ImportError:
    TEM_PIL = False

try:
    import psutil
    TEM_PSUTIL = True
except ImportError:
    TEM_PSUTIL = False

try:
    from ddgs import DDGS
    TEM_DDGS = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        TEM_DDGS = True
    except ImportError:
        TEM_DDGS = False

# Configurações de Ficheiros e Pastas
PASTA_ATUAL = os.path.dirname(os.path.abspath(__file__))
PASTA_IMAGENS = os.path.abspath(os.path.join(PASTA_ATUAL, "imagens_rubos"))
os.makedirs(PASTA_IMAGENS, exist_ok=True)

PASTA_SCRIPTS = os.path.abspath(os.path.join(PASTA_ATUAL, "scripts"))
os.makedirs(PASTA_SCRIPTS, exist_ok=True)

PASTA_VOZES_PIPER = os.path.join(PASTA_ATUAL, "vozes_piper")
os.makedirs(PASTA_VOZES_PIPER, exist_ok=True)
MODELO_PIPER_PADRAO = os.path.join(PASTA_VOZES_PIPER, "pt_PT-tugao-medium.onnx")

FICHEIRO_VETORIAL = os.path.join(PASTA_ATUAL, "base_vetorial_rubos.json")
FICHEIRO_MEMORIA_LEGADO = os.path.join(PASTA_ATUAL, "memoria_rubos.json")
FICHEIRO_AGENDA = os.path.join(PASTA_ATUAL, "agenda_rubos.json")
FICHEIRO_NOTAS = os.path.join(os.path.expanduser("~"), "Desktop", "notas_rubos.txt")
FLAG_SEM_JANELA = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# Estado global
historico_chat = []
modelos_instalados = []
apps_indexadas = {}
imagem_anexada_b64 = None
ultima_resposta_texto = ""
auto_web_ativo = True
voz_ativa = True

# Mapas de Dispositivos de Áudio { "Nome Visível": indice_sd_ou_None }
mapa_dispositivos_entrada = {"Padrão do Sistema": None}
mapa_dispositivos_saida = {"Padrão do Sistema": None}

# Controlo de processamento e interrupção de voz
pedido_atual_id = 0
ia_a_responder = False
ultimo_prompt_enviado_voz = ""
_parar_audio_tts = threading.Event()
_tts_a_falar = threading.Event()
_stream_saida_ativo = None
_lock_saida_audio = threading.Lock()
_lock_ollama_boot = threading.Lock()
_lock_agenda = threading.Lock()
_aviso_voz_pt_mostrado = False

# Escala tipográfica dinâmica
zoom_manual = 1.0
tamanho_fonte_atual = {
    "chat": 11,
    "input": 12,
    "btn": 9,
    "small": 8,
    "title": 14
}
_timer_resize = None

# Modelos Ollama com suporte de Visão
PALAVRAS_VISAO = (
    "llava", "vision", "minicpm", "moondream", "bakllava",
    "gemma3", "qwen2.5vl", "qwen2-vl", "pixtral", "granite3.2-vision"
)

# Paleta de Cores Moderna (Obsidian & Slate)
BG_APP = "#0d0f14"
BG_SIDEBAR = "#12151e"
BG_SURFACE = "#171b26"
BG_ELEVATED = "#1f2433"
BORDER_SUBTLE = "#2a3145"
BORDER_ACTIVE = "#475569"

TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"
TEXT_MUTED = "#64748b"

ACCENT_CYAN = "#38bdf8"
ACCENT_CYAN_HOVER = "#7dd3fc"
ACCENT_VIOLET = "#a78bfa"
ACCENT_VIOLET_HOVER = "#c4b5fd"
ACCENT_GREEN = "#34d399"
ACCENT_AMBER = "#fbbf24"
ACCENT_ROSE = "#fb7185"


# ==========================================
# 0. GESTÃO AUTOMÁTICA DO SERVIDOR OLLAMA
# ==========================================
def garantir_ollama_ativo(timeout_arranque=8.0):
    """
    Verifica se o Ollama está a responder em localhost:11434.
    Se estiver fechado (WinError 10061), inicia 'ollama serve' em segundo plano e aguarda ficar pronto.
    """
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
        if r.status_code == 200:
            return True
    except Exception:
        pass

    with _lock_ollama_boot:
        try:
            r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
            if r.status_code == 200:
                return True
        except Exception:
            pass

        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=FLAG_SEM_JANELA
            )
        except Exception:
            return False

        inicio = time.time()
        while time.time() - inicio < timeout_arranque:
            time.sleep(0.5)
            try:
                r = requests.get("http://localhost:11434/api/tags", timeout=1.5)
                if r.status_code == 200:
                    if not modelos_instalados:
                        try:
                            carregar_modelos_ollama()
                        except Exception:
                            pass
                    return True
            except Exception:
                continue

    return False


# ==========================================
# 1. PERMISSÕES DE ADMINISTRADOR (WINDOWS UAC)
# ==========================================
def eh_administrador():
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def reiniciar_como_administrador():
    if os.name != "nt":
        return
    if eh_administrador():
        messagebox.showinfo("Permissões", "O Rubos já está a correr com permissões totais de Administrador.")
        return
    try:
        pasta_python = os.path.dirname(sys.executable)
        pythonw = os.path.join(pasta_python, "pythonw.exe")
        exe_alvo = pythonw if os.path.exists(pythonw) else sys.executable
        parametros = f'"{os.path.abspath(__file__)}" --sem-consola'
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_alvo, parametros, PASTA_ATUAL, 1)
        if ret > 32:
            _ao_fechar_janela()
            sys.exit(0)
        else:
            messagebox.showwarning("Permissões", "A elevação para Administrador foi cancelada.")
    except Exception as e:
        messagebox.showerror("Erro de Permissões", f"Não foi possível pedir permissões de Administrador: {e}")


def executar_como_admin(caminho_ou_cmd, argumentos=""):
    if os.name != "nt":
        subprocess.Popen([caminho_ou_cmd])
        return True
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", caminho_ou_cmd, argumentos, None, 1)
        return ret > 32
    except Exception:
        return False


# ==========================================
# 2. BASE DE DADOS VETORIAL PRIVADA (RAG LOCAL)
# ==========================================
def _gerar_vetor_fallback(texto, dim=256):
    vetor = [0.0] * dim
    tokens = re.findall(r"[a-zA-ZÀ-ÿ0-9_]{2,}", texto.lower())
    for tok in tokens:
        idx = hash(tok) % dim
        vetor[idx] += 1.0
    norma = math.sqrt(sum(v * v for v in vetor))
    return [v / norma for v in vetor] if norma > 0 else vetor


def gerar_embedding_ollama(texto):
    texto_limpo = texto.strip()[:3000]
    if not texto_limpo:
        return []
    modelos_emb = ["nomic-embed-text", "mxbai-embed-large", "all-minilm"]
    for m in modelos_instalados:
        if "embed" in m.lower() and m not in modelos_emb:
            modelos_emb.insert(0, m)

    for modelo_emb in modelos_emb:
        try:
            res = requests.post(
                "http://localhost:11434/api/embeddings",
                json={"model": modelo_emb, "prompt": texto_limpo},
                timeout=3
            )
            if res.status_code == 200:
                emb = res.json().get("embedding", [])
                if emb:
                    return emb
        except Exception:
            continue

    return _gerar_vetor_fallback(texto_limpo)


def similaridade_cosseno(v1, v2):
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def carregar_base_vetorial():
    registos = []
    if os.path.exists(FICHEIRO_VETORIAL):
        try:
            with open(FICHEIRO_VETORIAL, "r", encoding="utf-8") as f:
                registos = json.load(f)
        except Exception:
            registos = []

    if os.path.exists(FICHEIRO_MEMORIA_LEGADO):
        try:
            with open(FICHEIRO_MEMORIA_LEGADO, "r", encoding="utf-8") as f:
                antigas = json.load(f)
            existentes = {r.get("texto", "") for r in registos}
            for item in antigas:
                if item and item not in existentes:
                    registos.append({
                        "texto": item,
                        "origem": "Memória Pessoal",
                        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
                        "vetor": gerar_embedding_ollama(item)
                    })
            guardar_base_vetorial(registos)
            os.remove(FICHEIRO_MEMORIA_LEGADO)
        except Exception:
            pass

    return registos


def guardar_base_vetorial(registos):
    with open(FICHEIRO_VETORIAL, "w", encoding="utf-8") as f:
        json.dump(registos, f, ensure_ascii=False, indent=2)


def adicionar_a_base_vetorial(texto, origem="Memória Pessoal"):
    registos = carregar_base_vetorial()
    texto = texto.strip()
    if not texto:
        return
    if any(r.get("texto") == texto and r.get("origem") == origem for r in registos):
        return
    vetor = gerar_embedding_ollama(texto)
    registos.append({
        "texto": texto,
        "origem": origem,
        "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "vetor": vetor
    })
    guardar_base_vetorial(registos)


def indexar_ficheiro_na_base_vetorial(caminho):
    nome = os.path.basename(caminho)
    try:
        with open(caminho, "r", encoding="utf-8", errors="ignore") as f:
            conteudo = f.read()
    except Exception as e:
        return 0, f"Erro ao ler ficheiro: {e}"

    conteudo = re.sub(r"\n{3,}", "\n\n", conteudo).strip()
    if not conteudo:
        return 0, "O ficheiro está vazio."

    tamanho_bloco = 900
    sobreposicao = 150
    blocos = []
    inicio = 0
    while inicio < len(conteudo):
        fim = inicio + tamanho_bloco
        bloco = conteudo[inicio:fim].strip()
        if bloco:
            blocos.append(bloco)
        inicio += tamanho_bloco - sobreposicao

    registos = carregar_base_vetorial()
    registos = [r for r in registos if r.get("origem") != f"Ficheiro: {nome}"]

    for idx, bloco in enumerate(blocos[:40], 1):
        registos.append({
            "texto": f"[{nome} - Parte {idx}] {bloco}",
            "origem": f"Ficheiro: {nome}",
            "data": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "vetor": gerar_embedding_ollama(bloco)
        })

    guardar_base_vetorial(registos)
    return min(len(blocos), 40), ""


def pesquisar_base_vetorial(pergunta, top_k=4):
    registos = carregar_base_vetorial()
    if not registos:
        return ""
    vetor_query = gerar_embedding_ollama(pergunta)
    pontuados = []
    for r in registos:
        vet = r.get("vetor", [])
        if len(vet) != len(vetor_query):
            vet = _gerar_vetor_fallback(r.get("texto", ""), len(vetor_query))
        score = similaridade_cosseno(vetor_query, vet)
        if score > 0.12:
            pontuados.append((score, r))

    pontuados.sort(key=lambda x: x[0], reverse=True)
    melhores = pontuados[:top_k]
    if not melhores:
        return ""
    return "\n".join([f"- ({r.get('origem')}) {r.get('texto')}" for _, r in melhores])


def limpar_base_vetorial():
    if os.path.exists(FICHEIRO_VETORIAL):
        os.remove(FICHEIRO_VETORIAL)


# ==========================================
# 2.5 GESTÃO DE AGENDA, CALENDÁRIO E LEMBRETES PROATIVOS
# ==========================================
DIAS_SEMANA_PT = {
    "segunda": 0, "segunda-feira": 0,
    "terça": 1, "terca": 1, "terça-feira": 1, "terca-feira": 1,
    "quarta": 2, "quarta-feira": 2,
    "quinta": 3, "quinta-feira": 3,
    "sexta": 4, "sexta-feira": 4,
    "sábado": 5, "sabado": 5,
    "domingo": 6
}
NOMES_DIAS_PT = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]


def carregar_agenda():
    with _lock_agenda:
        if not os.path.exists(FICHEIRO_AGENDA):
            return []
        try:
            with open(FICHEIRO_AGENDA, "r", encoding="utf-8") as f:
                dados = json.load(f)
                return dados if isinstance(dados, list) else []
        except Exception:
            return []


def guardar_agenda(eventos):
    with _lock_agenda:
        with open(FICHEIRO_AGENDA, "w", encoding="utf-8") as f:
            json.dump(eventos, f, ensure_ascii=False, indent=2)


def _extrair_data_hora_pt(texto):
    """
    Interpreta datas e horas naturais em português (hoje, amanhã, depois de amanhã,
    dias da semana, DD/MM, DD/MM/YYYY, HH:MM, HHhMM, às HH) e devolve:
    (data_iso 'YYYY-MM-DD' ou None, hora_str 'HH:MM' ou None, titulo_limpo).
    """
    agora = datetime.now()
    data_alvo = None
    hora_alvo = None
    resto = " " + texto.strip() + " "

    # 1. Data relativa: depois de amanhã / amanhã / hoje
    if re.search(r"\bdepois\s+de\s+amanh[ãa]\b", resto, re.I):
        data_alvo = (agora + timedelta(days=2)).date()
        resto = re.sub(r"\b(?:de|para|no\s+dia)?\s*depois\s+de\s+amanh[ãa]\b", " ", resto, flags=re.I)
    elif re.search(r"\bamanh[ãa]\b", resto, re.I):
        data_alvo = (agora + timedelta(days=1)).date()
        resto = re.sub(r"\b(?:de|para|no\s+dia)?\s*amanh[ãa]\b", " ", resto, flags=re.I)
    elif re.search(r"\bhoje\b", resto, re.I):
        data_alvo = agora.date()
        resto = re.sub(r"\b(?:de|para|no\s+dia)?\s*hoje\b", " ", resto, flags=re.I)

    # 2. Data explícita DD/MM ou DD/MM/YYYY ou DD-MM
    if data_alvo is None:
        m_data = re.search(r"\b(?:dia\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", resto, re.I)
        if m_data:
            dia = int(m_data.group(1))
            mes = int(m_data.group(2))
            ano_raw = m_data.group(3)
            if ano_raw:
                ano = int(ano_raw) if len(ano_raw) == 4 else 2000 + int(ano_raw)
            else:
                ano = agora.year
            try:
                candidata = datetime(ano, mes, dia).date()
                if not ano_raw and candidata < agora.date():
                    candidata = datetime(ano + 1, mes, dia).date()
                data_alvo = candidata
                resto = resto[:m_data.start()] + " " + resto[m_data.end():]
            except ValueError:
                pass

    # 3. Dia da semana (ex: "na sexta", "segunda-feira")
    if data_alvo is None:
        for nome_dia, idx_dia in DIAS_SEMANA_PT.items():
            m_ds = re.search(rf"\b(?:na|no|pr[óo]xim[ao]|esta|este)?\s*{re.escape(nome_dia)}\b", resto, re.I)
            if m_ds:
                diff = (idx_dia - agora.weekday()) % 7
                if diff == 0:
                    diff = 7
                data_alvo = (agora + timedelta(days=diff)).date()
                resto = resto[:m_ds.start()] + " " + resto[m_ds.end():]
                break

    # 4. Hora: "às 9:30", "as 09h30", "9:30", "às 14 horas", "às 15"
    m_hora = re.search(r"\b(?:[àa]s|pelas)?\s*(\d{1,2})\s*[:hH]\s*(\d{2})\b", resto)
    if m_hora:
        hh, mm = int(m_hora.group(1)), int(m_hora.group(2))
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            hora_alvo = f"{hh:02d}:{mm:02d}"
            resto = resto[:m_hora.start()] + " " + resto[m_hora.end():]
    else:
        m_hora_simples = re.search(r"\b(?:[àa]s|pelas)\s+(\d{1,2})(?:\s*horas?)?\b", resto, re.I)
        if m_hora_simples:
            hh = int(m_hora_simples.group(1))
            if 0 <= hh <= 23:
                hora_alvo = f"{hh:02d}:00"
                resto = resto[:m_hora_simples.start()] + " " + resto[m_hora_simples.end():]

    if data_alvo is None and hora_alvo is not None:
        hh_i, mm_i = map(int, hora_alvo.split(":"))
        dt_teste = agora.replace(hour=hh_i, minute=mm_i, second=0, microsecond=0)
        data_alvo = agora.date() if dt_teste >= agora else (agora + timedelta(days=1)).date()
    elif data_alvo is None:
        data_alvo = agora.date()

    titulo = re.sub(r"\s+", " ", resto).strip(" ,.-:;")
    titulo = re.sub(r"^(?:de|do|da|para|sobre|que\s+tenho|tenho)\s+", "", titulo, flags=re.I).strip()
    if not titulo:
        titulo = "Compromisso"

    return data_alvo.isoformat(), hora_alvo, titulo


def _formatar_data_pt(data_iso):
    try:
        d = datetime.strptime(data_iso, "%Y-%m-%d").date()
        hoje = datetime.now().date()
        if d == hoje:
            return f"Hoje ({d.strftime('%d/%m/%Y')})"
        if d == hoje + timedelta(days=1):
            return f"Amanhã ({d.strftime('%d/%m/%Y')})"
        return f"{NOMES_DIAS_PT[d.weekday()].capitalize()}, {d.strftime('%d/%m/%Y')}"
    except Exception:
        return data_iso


def adicionar_evento_agenda(texto_pedido):
    data_iso, hora_str, titulo = _extrair_data_hora_pt(texto_pedido)
    eventos = carregar_agenda()
    novo = {
        "id": int(time.time() * 1000),
        "titulo": titulo,
        "data": data_iso,
        "hora": hora_str,
        "notificado": False,
        "criado_em": datetime.now().strftime("%d/%m/%Y %H:%M")
    }
    eventos.append(novo)
    eventos.sort(key=lambda e: (e.get("data") or "9999-12-31", e.get("hora") or "23:59"))
    guardar_agenda(eventos)

    hora_txt = f" às {hora_str}" if hora_str else ""
    data_txt = _formatar_data_pt(data_iso)
    adicionar_a_base_vetorial(f"Evento na agenda: {titulo} — {data_txt}{hora_txt}", origem="Agenda")
    return f"Agendado: '{titulo}' para {data_txt}{hora_txt}."


def consultar_agenda_texto(filtro="todos"):
    eventos = carregar_agenda()
    hoje_iso = datetime.now().date().isoformat()
    amanha_iso = (datetime.now().date() + timedelta(days=1)).isoformat()

    if filtro == "hoje":
        filtrados = [e for e in eventos if e.get("data") == hoje_iso]
        cabecalho = "Eventos na tua agenda para hoje:"
        vazio = "Não tens nenhum evento marcado para hoje."
    elif filtro == "amanha":
        filtrados = [e for e in eventos if e.get("data") == amanha_iso]
        cabecalho = "Eventos na tua agenda para amanhã:"
        vazio = "Não tens nenhum evento marcado para amanhã."
    else:
        filtrados = [e for e in eventos if (e.get("data") or "") >= hoje_iso]
        cabecalho = "Próximos eventos na tua agenda:"
        vazio = "A tua agenda está livre — não tens eventos futuros marcados."

    if not filtrados:
        return vazio

    linhas = []
    for e in filtrados:
        h_str = f" às {e['hora']}" if e.get("hora") else ""
        linhas.append(f"• {_formatar_data_pt(e['data'])}{h_str} — {e['titulo']}")
    return cabecalho + "\n" + "\n".join(linhas)


def remover_evento_agenda(termo):
    termo_low = termo.lower().strip()
    eventos = carregar_agenda()
    if not eventos:
        return "A tua agenda já está vazia."

    if termo_low in ("todos", "tudo", "toda a agenda", "agenda"):
        guardar_agenda([])
        return "Limpei todos os eventos da tua agenda."

    restantes = [e for e in eventos if termo_low not in e.get("titulo", "").lower()]
    removidos = len(eventos) - len(restantes)
    if removidos == 0:
        return f"Não encontrei nenhum evento na agenda com '{termo}'."

    guardar_agenda(restantes)
    return f"Removi {removidos} evento(s) correspondente(s) a '{termo}' da agenda."


def resumo_agenda_para_llm(limite=8):
    eventos = carregar_agenda()
    hoje_iso = datetime.now().date().isoformat()
    futuros = [e for e in eventos if (e.get("data") or "") >= hoje_iso][:limite]
    if not futuros:
        return "Sem eventos futuros agendados."
    return "\n".join([
        f"- {_formatar_data_pt(e['data'])}{(' às ' + e['hora']) if e.get('hora') else ''}: {e['titulo']}"
        for e in futuros
    ])


def _ciclo_monitor_agenda():
    """Verifica a cada 20s se algum evento agendado chegou à hora e notifica com voz + chat."""
    while True:
        try:
            agora = datetime.now()
            hoje_iso = agora.date().isoformat()
            hora_atual = agora.strftime("%H:%M")
            eventos = carregar_agenda()
            alterou = False

            for ev in eventos:
                if ev.get("notificado"):
                    continue
                if ev.get("data") == hoje_iso and ev.get("hora") == hora_atual:
                    ev["notificado"] = True
                    alterou = True
                    msg_alerta = f"⏰ Lembrete da Agenda ({hora_atual}): {ev.get('titulo')}"
                    if "area_chat" in globals():
                        adicionar_ao_chat("Rubos", msg_alerta, "bot_tag")
                    falar_com_piper(f"Rodrigo, tens agora na agenda: {ev.get('titulo')}.")

            if alterou:
                guardar_agenda(eventos)
        except Exception:
            pass
        time.sleep(20)


# ==========================================
# 3. CONTROLO TOTAL DE JANELAS, PROCESSOS E SISTEMA WINDOWS
# ==========================================
def listar_janelas_abertas():
    janelas = []
    if os.name != "nt":
        return janelas

    user32 = ctypes.windll.user32
    EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    ignoradas = {"Program Manager", "Windows Input Experience", "Settings", "Configurações", "Microsoft Text Input Application"}

    def callback(hwnd, lParam):
        if user32.IsWindowVisible(hwnd):
            tamanho = user32.GetWindowTextLengthW(hwnd)
            if tamanho > 0:
                buf = ctypes.create_unicode_buffer(tamanho + 1)
                user32.GetWindowTextW(hwnd, buf, tamanho + 1)
                titulo = buf.value.strip()
                if titulo and titulo not in ignoradas and not titulo.startswith("Rubos AI"):
                    pid = ctypes.c_ulong()
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    proc_nome = ""
                    if TEM_PSUTIL:
                        try:
                            proc_nome = psutil.Process(pid.value).name()
                        except Exception:
                            pass
                    janelas.append({
                        "hwnd": hwnd,
                        "titulo": titulo,
                        "pid": pid.value,
                        "processo": proc_nome
                    })
        return True

    user32.EnumWindows(EnumWindowsProc(callback), 0)
    return janelas


def _forcar_terminar_executavel(nome_exe, pid=None):
    sucesso = False
    if os.name == "nt" and nome_exe:
        try:
            res = subprocess.run(
                ["taskkill", "/F", "/T", "/IM", nome_exe],
                capture_output=True, text=True, timeout=6, creationflags=FLAG_SEM_JANELA
            )
            if res.returncode == 0:
                sucesso = True
        except Exception:
            pass
    if not sucesso and TEM_PSUTIL and pid:
        try:
            proc = psutil.Process(pid)
            proc.kill()
            sucesso = True
        except Exception:
            pass
    return sucesso


def controlar_janela(alvo, acao="fechar", forcar=False):
    alvo_low = alvo.lower().strip()
    if not alvo_low:
        return False, "Não indicaste qual a janela ou aplicação."

    aliases = {
        "bloco de notas": "notepad",
        "calculadora": "calculator",
        "explorador": "explorer",
        "explorador de ficheiros": "explorer",
        "gestor de tarefas": "taskmgr",
        "navegador": "chrome",
        "unreal": "unrealeditor",
        "unreal engine": "unrealeditor",
        "vs code": "code",
        "visual studio code": "code",
        "word": "winword",
        "excel": "excel",
        "powerpoint": "powerpnt",
        "nvidia geforce overlay": "nvidia overlay",
        "geforce overlay": "nvidia overlay"
    }
    termo_extra = aliases.get(alvo_low, alvo_low)

    janelas = listar_janelas_abertas()
    correspondencias = []
    for j in janelas:
        t_low = j["titulo"].lower()
        p_low = j["processo"].lower().replace(".exe", "")
        if alvo_low in t_low or termo_extra in t_low or alvo_low in p_low or termo_extra in p_low:
            correspondencias.append(j)

    user32 = ctypes.windll.user32

    if correspondencias:
        afetadas = []
        falhadas = []
        for j in correspondencias:
            hwnd = j["hwnd"]
            proc_nome = j.get("processo", "")
            proc_limpo = proc_nome.lower().replace(".exe", "")
            eh_protegido = ("taskmgr" in proc_limpo) or ("gestor de tarefas" in j["titulo"].lower())

            if acao == "fechar":
                if not eh_protegido:
                    user32.PostMessageW(hwnd, 0x0010, 0, 0)
                    time.sleep(0.15)

                if forcar or eh_protegido or user32.IsWindow(hwnd):
                    exe_alvo = proc_nome or ("Taskmgr.exe" if eh_protegido else "")
                    if exe_alvo and proc_limpo != "explorer":
                        _forcar_terminar_executavel(exe_alvo, j.get("pid"))
                        time.sleep(0.1)

                if not user32.IsWindow(hwnd):
                    afetadas.append(j["titulo"])
                else:
                    falhadas.append(j["titulo"])
            elif acao == "focar":
                user32.ShowWindow(hwnd, 9)
                user32.SetForegroundWindow(hwnd)
                afetadas.append(j["titulo"])
            elif acao == "minimizar":
                user32.ShowWindow(hwnd, 6)
                afetadas.append(j["titulo"])
            elif acao == "maximizar":
                user32.ShowWindow(hwnd, 3)
                user32.SetForegroundWindow(hwnd)
                afetadas.append(j["titulo"])

        nomes_unicos = list(dict.fromkeys(afetadas))
        if nomes_unicos:
            verbo = {
                "fechar": "Fechei",
                "focar": "Coloquei em primeiro plano",
                "minimizar": "Minimizei",
                "maximizar": "Maximizei"
            }.get(acao, "Atualizei")
            extra_f = ""
            if falhadas:
                extra_f = f" (Nota: {', '.join(set(falhadas))} exige permissões de Administrador para fechar.)"
            return True, f"{verbo}: {', '.join(nomes_unicos[:5])}.{extra_f}"

        if falhadas:
            return True, (
                f"Não consegui fechar '{', '.join(set(falhadas))}' porque está a correr com privilégios elevados. "
                f"Ativa o botão '🛡️ Admin' na barra lateral se quiseres fechar processos de sistema."
            )

    if acao == "fechar":
        if "taskmgr" in alvo_low or "taskmgr" in termo_extra or "gestor de tarefas" in alvo_low:
            if _forcar_terminar_executavel("Taskmgr.exe"):
                return True, "Fechei o Gestor de Tarefas."
            return True, "O Gestor de Tarefas não estava aberto ou exige permissões de Administrador."

        if TEM_PSUTIL:
            encerrados = []
            for proc in psutil.process_iter(["pid", "name"]):
                try:
                    p_name = (proc.info["name"] or "").lower()
                    p_clean = p_name.replace(".exe", "")
                    if alvo_low == p_clean or termo_extra == p_clean or (len(alvo_low) >= 4 and alvo_low in p_clean):
                        if p_clean not in ("explorer", "svchost", "csrss", "wininit", "lsass", "python", "pythonw"):
                            _forcar_terminar_executavel(proc.info["name"], proc.info["pid"])
                            encerrados.append(proc.info["name"])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            if encerrados:
                return True, f"Encerrei o processo: {', '.join(set(encerrados))}."

    return False, f"Não encontrei nenhuma janela ou aplicação aberta com o nome '{alvo}'."


def _enviar_tecla_media_windows(vk_code, repeticoes=1):
    if os.name != "nt":
        return False
    try:
        user32 = ctypes.windll.user32
        for _ in range(max(1, repeticoes)):
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, 2, 0)
            time.sleep(0.03)
        return True
    except Exception:
        return False


def _calcular_expressao_segura(expr):
    """Calcula expressões aritméticas básicas com segurança via AST."""
    ops = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def _eval(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in ops:
            return ops[type(node.op)](_eval(node.operand))
        raise ValueError("Expressão não suportada")

    expr_clean = expr.replace("x", "*").replace("X", "*").replace("÷", "/").replace(",", ".")
    tree = ast.parse(expr_clean, mode="eval")
    return _eval(tree.body)


def executar_script_personalizado(nome_script, argumentos=""):
    """Executa um script .py localizado na pasta 'scripts' do Rubos."""
    if not nome_script.endswith(".py"):
        nome_script += ".py"
    caminho = os.path.join(PASTA_SCRIPTS, os.path.basename(nome_script))
    if not os.path.exists(caminho):
        return False, f"Não encontrei o script '{nome_script}' na pasta '{PASTA_SCRIPTS}'."

    try:
        args_lista = shlex.split(argumentos) if argumentos else []
        res = subprocess.run(
            [sys.executable, caminho] + args_lista,
            cwd=PASTA_SCRIPTS,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=FLAG_SEM_JANELA
        )
        saida = (res.stdout or "").strip()
        erro = (res.stderr or "").strip()
        if res.returncode == 0:
            return True, saida if saida else f"Script '{nome_script}' executado com sucesso."
        return True, f"O script '{nome_script}' terminou com aviso/erro:\n{erro or saida}"
    except subprocess.TimeoutExpired:
        return True, f"O script '{nome_script}' excedeu o tempo limite de 30 segundos."
    except Exception as e:
        return True, f"Erro ao executar '{nome_script}': {e}"


# ==========================================
# 4. INDEXADOR GLOBAL DE APLICAÇÕES E FICHEIROS DO PC
# ==========================================
def indexar_aplicacoes_windows():
    global apps_indexadas
    mapa = {}

    def registar(nome, alvo, tipo="path"):
        chave = re.sub(r"\s+", " ", nome.lower()).strip()
        if chave and len(chave) > 1:
            mapa[chave] = {"nome": nome.strip(), "alvo": alvo, "tipo": tipo}

    nativas = {
        "calculadora": ("Calculadora", "calc.exe", "cmd"),
        "bloco de notas": ("Bloco de Notas", "notepad.exe", "cmd"),
        "notepad": ("Bloco de Notas", "notepad.exe", "cmd"),
        "paint": ("Paint", "mspaint.exe", "cmd"),
        "explorador de ficheiros": ("Explorador de Ficheiros", "explorer.exe", "cmd"),
        "pastas": ("Explorador de Ficheiros", "explorer.exe", "cmd"),
        "gestor de tarefas": ("Gestor de Tarefas", "taskmgr.exe", "cmd"),
        "cmd": ("Linha de Comandos (CMD)", "cmd.exe", "cmd"),
        "terminal": ("Windows Terminal", "wt.exe", "cmd"),
        "powershell": ("PowerShell", "powershell.exe", "cmd"),
        "definições": ("Definições do Windows", "ms-settings:", "path"),
        "configurações": ("Definições do Windows", "ms-settings:", "path"),
        "painel de controlo": ("Painel de Controlo", "control.exe", "cmd"),
        "ferramenta de recorte": ("Ferramenta de Recorte", "snippingtool.exe", "cmd"),
    }
    for k, (n, a, t) in nativas.items():
        registar(k, a, t)

    if os.name == "nt":
        pastas_atalhos = [
            os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
            os.path.join(os.path.expanduser("~"), "Desktop"),
            os.path.join(os.environ.get("PUBLIC", r"C:\Users\Public"), "Desktop"),
        ]
        for base in pastas_atalhos:
            if not os.path.exists(base):
                continue
            for raiz, _, ficheiros in os.walk(base):
                for f in ficheiros:
                    if f.lower().endswith((".lnk", ".url", ".exe")):
                        nome_limpo = os.path.splitext(f)[0]
                        if not any(x in nome_limpo.lower() for x in ("uninstall", "desinstalar", "readme", "help", "manual")):
                            registar(nome_limpo, os.path.join(raiz, f), "path")

        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                chave_reg = winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
                num_sub = winreg.QueryInfoKey(chave_reg)[0]
                for i in range(num_sub):
                    sub_nome = winreg.EnumKey(chave_reg, i)
                    try:
                        sub_key = winreg.OpenKey(chave_reg, sub_nome)
                        caminho_exe, _ = winreg.QueryValueEx(sub_key, "")
                        caminho_exe = caminho_exe.strip('"')
                        if os.path.exists(caminho_exe):
                            nome_app = os.path.splitext(sub_nome)[0]
                            registar(nome_app, caminho_exe, "path")
                    except Exception:
                        continue
            except Exception:
                continue

        try:
            ps = "Get-StartApps | ConvertTo-Json -Compress"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                capture_output=True, text=True, timeout=8, creationflags=FLAG_SEM_JANELA
            )
            if res.returncode == 0 and res.stdout.strip():
                dados_uwp = json.loads(res.stdout)
                if isinstance(dados_uwp, dict):
                    dados_uwp = [dados_uwp]
                for app in dados_uwp:
                    nome_uwp = app.get("Name", "").strip()
                    app_id = app.get("AppID", "").strip()
                    if nome_uwp and app_id:
                        chave = nome_uwp.lower()
                        if chave not in mapa:
                            registar(nome_uwp, app_id, "uwp")
        except Exception:
            pass

    apps_indexadas = mapa


def abrir_aplicacao_pc(nome_pedido, como_admin=False):
    termo = nome_pedido.lower().strip()
    if not apps_indexadas:
        indexar_aplicacoes_windows()

    escolha = apps_indexadas.get(termo)

    if not escolha:
        candidatos = [v for k, v in apps_indexadas.items() if termo in k or k in termo]
        if candidatos:
            candidatos.sort(key=lambda x: len(x["nome"]))
            escolha = candidatos[0]

    if not escolha and apps_indexadas:
        parecidos = difflib.get_close_matches(termo, list(apps_indexadas.keys()), n=1, cutoff=0.6)
        if parecidos:
            escolha = apps_indexadas[parecidos[0]]

    if escolha:
        alvo = escolha["alvo"]
        tipo = escolha["tipo"]
        nome_real = escolha["nome"]
        try:
            if como_admin and tipo in ("path", "cmd"):
                ok = executar_como_admin(alvo)
                if ok:
                    return True, f"Abri '{nome_real}' com permissões de Administrador."
            if tipo == "uwp":
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{alvo}"])
            elif tipo == "cmd":
                subprocess.Popen(alvo, shell=True)
            else:
                os.startfile(alvo)
            return True, f"Abri a aplicação: {nome_real}."
        except Exception as e:
            return False, f"Encontrei '{nome_real}', mas ocorreu um erro ao abrir: {e}"

    return False, ""


def procurar_ficheiros_pc(termo, limite=6):
    termo_low = termo.lower().strip().strip('"').strip("'")
    if not termo_low:
        return []

    if os.path.exists(termo_low):
        return [os.path.abspath(termo_low)]

    home = os.path.expanduser("~")
    pastas_raiz = [
        PASTA_ATUAL,
        PASTA_IMAGENS,
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Videos"),
        os.path.join(home, "Music"),
    ]
    pastas_ignoradas = {
        ".git", "node_modules", "__pycache__", "AppData", "Intermediate",
        "Saved", "Binaries", "DerivedDataCache", ".vs", "venv", ".venv"
    }

    encontrados = []
    vistas = set()

    for raiz_base in pastas_raiz:
        if not os.path.exists(raiz_base):
            continue
        profundidade_base = raiz_base.rstrip(os.sep).count(os.sep)

        for raiz, dirs, ficheiros in os.walk(raiz_base):
            dirs[:] = [d for d in dirs if d not in pastas_ignoradas and not d.startswith(".")]
            if raiz.count(os.sep) - profundidade_base > 4:
                dirs[:] = []
                continue

            for d in dirs:
                if termo_low in d.lower():
                    caminho_d = os.path.join(raiz, d)
                    if caminho_d not in vistas:
                        vistas.add(caminho_d)
                        encontrados.append(caminho_d)

            for f in ficheiros:
                if termo_low in f.lower():
                    caminho_f = os.path.join(raiz, f)
                    if caminho_f not in vistas:
                        vistas.add(caminho_f)
                        encontrados.append(caminho_f)

            if len(encontrados) >= limite * 2:
                break

    encontrados.sort(key=lambda p: (os.path.basename(p).lower() != termo_low, len(os.path.basename(p))))
    return encontrados[:limite]


# ==========================================
# 5. PESQUISA, DOWNLOAD E ABERTURA DE IMAGENS
# ==========================================
def extrair_termo_pesquisa(texto):
    limpo = texto.strip().replace("–", "-").replace("—", "-")
    limpo = re.sub(r"[?.!]+$", "", limpo).strip()

    limpo = re.sub(
        r"^(?:por\s+favor\s+)?(?:podes\s+|consegues\s+)?"
        r"(?:mostra(?:-me)?|manda(?:-me)?|envia(?:-me)?|pesquisa|procura|busca|quero\s+ver|encontra|traz(?:-me)?|d[áa](?:-me)?|ver)\b\s*",
        "",
        limpo,
        flags=re.I
    )

    limpo = re.sub(r"^(?:no\s+google|na\s+internet|na\s+web)\b\s*", "", limpo, flags=re.I)

    limpo = re.sub(
        r"^(?:algumas\s+|umas\s+|uns\s+|uma\s+|um\s+|o\s+|a\s+|os\s+|as\s+)?"
        r"(?:imagens?|fotos?|fotografias?|desenhos?|ilustra[çc][õo]es?|wallpapers?|fundos?|figuras?|logos?|logotipos?|emblemas?|s[íi]mbolos?)\b\s*"
        r"(?:de|do|da|dos|das|sobre|com)?\s*",
        "",
        limpo,
        flags=re.I
    )

    limpo = re.sub(r"\s+(?:no\s+google|na\s+internet|na\s+web)$", "", limpo, flags=re.I).strip()
    return limpo if limpo else texto.strip()


def abrir_ficheiro_no_windows(caminho, como_admin=False):
    try:
        if como_admin and os.name == "nt":
            if executar_como_admin(caminho):
                return
        os.startfile(caminho)
    except Exception:
        try:
            subprocess.Popen(["explorer", caminho])
        except Exception:
            webbrowser.open(f"file:///{caminho}")


def detetar_extensao_imagem(dados_bytes):
    if dados_bytes.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if dados_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if dados_bytes.startswith(b"RIFF") and dados_bytes[8:12] == b"WEBP":
        return ".webp"
    if dados_bytes.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    return None


def pesquisar_e_abrir_imagens(query, limite=3):
    termo = extrair_termo_pesquisa(query)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8"
    }
    candidatos = []

    try:
        url_bing = f"https://www.bing.com/images/async?q={urllib.parse.quote(termo)}&first=0&count=15&adlt=moderate"
        res_b = requests.get(url_bing, headers=headers, timeout=6)
        murls = re.findall(r'murl&quot;:&quot;(https?://[^&]+?)&quot;', res_b.text)
        turls = re.findall(r'turl&quot;:&quot;(https?://[^&]+?)&quot;', res_b.text)
        for i, m_u in enumerate(murls[:12]):
            t_u = turls[i] if i < len(turls) else ""
            candidatos.append((m_u, t_u, termo))
    except Exception:
        pass

    if len(candidatos) < limite and TEM_DDGS:
        try:
            with DDGS() as ddgs:
                for r in ddgs.images(termo, max_results=10):
                    candidatos.append((
                        r.get("image", ""),
                        r.get("thumbnail", ""),
                        r.get("title", termo)
                    ))
        except Exception:
            pass

    if len(candidatos) < limite:
        try:
            res_wp = requests.get(
                "https://pt.wikipedia.org/w/api.php",
                params={
                    "action": "query",
                    "generator": "search",
                    "gsrsearch": termo,
                    "gsrlimit": 5,
                    "prop": "pageimages",
                    "piprop": "original|thumbnail",
                    "pithumbsize": 800,
                    "format": "json"
                },
                headers=headers,
                timeout=5
            ).json()
            for page in res_wp.get("query", {}).get("pages", {}).values():
                orig = page.get("original", {}).get("source", "")
                thumb = page.get("thumbnail", {}).get("source", "")
                if orig or thumb:
                    candidatos.append((orig, thumb, page.get("title", termo)))
        except Exception:
            pass

    ficheiros_guardados = []
    urls_vistas = set()
    slug = re.sub(r"[^a-zA-Z0-9_-]", "_", termo)[:25].strip("_") or "imagem"
    timestamp = int(time.time())

    for url_principal, url_thumb, titulo in candidatos:
        if len(ficheiros_guardados) >= limite:
            break

        for url_tentativa in [url_principal, url_thumb]:
            if not url_tentativa or url_tentativa in urls_vistas:
                continue
            urls_vistas.add(url_tentativa)
            try:
                dominio = urllib.parse.urlparse(url_tentativa).netloc
                req_headers = {**headers, "Referer": f"https://{dominio}/"}
                resp_img = requests.get(url_tentativa, headers=req_headers, timeout=6)
                dados = resp_img.content

                if resp_img.status_code != 200 or len(dados) < 2500:
                    continue

                idx = len(ficheiros_guardados) + 1
                if TEM_PIL:
                    pil_img = Image.open(io.BytesIO(dados)).convert("RGB")
                    if pil_img.width < 80 or pil_img.height < 80:
                        continue
                    caminho_final = os.path.join(PASTA_IMAGENS, f"{slug}_{timestamp}_{idx}.jpg")
                    pil_img.save(caminho_final, format="JPEG", quality=92)
                else:
                    ext = detetar_extensao_imagem(dados)
                    if not ext:
                        continue
                    caminho_final = os.path.join(PASTA_IMAGENS, f"{slug}_{timestamp}_{idx}{ext}")
                    with open(caminho_final, "wb") as f:
                        f.write(dados)

                ficheiros_guardados.append((caminho_final, titulo))
                if idx <= 2:
                    abrir_ficheiro_no_windows(caminho_final)
                    time.sleep(0.25)
                break
            except Exception:
                continue

    if not ficheiros_guardados:
        return [], termo, f"Não consegui descarregar ficheiros válidos para '{termo}'."

    return ficheiros_guardados, termo, ""


def listar_ultimas_imagens_guardadas(limite=5):
    try:
        ficheiros = [
            os.path.join(PASTA_IMAGENS, f)
            for f in os.listdir(PASTA_IMAGENS)
            if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))
        ]
        ficheiros.sort(key=os.path.getmtime, reverse=True)
        return [(c, os.path.basename(c)) for c in ficheiros[:limite]]
    except Exception:
        return []


# ==========================================
# 6. ACESSO À INTERNET (TEXTO, NOTÍCIAS, LINKS)
# ==========================================
def pesquisar_na_internet(query):
    resultados = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    if TEM_DDGS:
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, region="pt-pt", max_results=4):
                    resultados.append(f"[Web] {r.get('title')}: {r.get('body')}")
        except Exception:
            pass
    else:
        try:
            url_ddg = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            res = requests.get(url_ddg, headers=headers, timeout=5)
            snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', res.text, re.S)
            for s in snippets[:3]:
                limpo = re.sub(r"<.*?>", "", s).strip()
                if limpo:
                    resultados.append(f"[Web] {limpo}")
        except Exception:
            pass

    try:
        url_wiki = (
            f"https://pt.wikipedia.org/w/api.php?action=query&list=search"
            f"&srsearch={urllib.parse.quote(query)}&format=json&utf8=1"
        )
        res_w = requests.get(url_wiki, headers=headers, timeout=4).json()
        for item in res_w.get("query", {}).get("search", [])[:2]:
            titulo = item.get("title", "")
            snippet = re.sub(r"<.*?>", "", item.get("snippet", ""))
            resultados.append(f"[Wikipédia - {titulo}] {snippet}")
    except Exception:
        pass

    return "\n".join(resultados) if resultados else "Sem resultados relevantes encontrados na pesquisa."


def obter_noticias_atuais():
    try:
        url_rss = "https://news.google.com/rss?hl=pt-PT&gl=PT&ceid=PT:pt-150"
        res = requests.get(url_rss, timeout=4)
        root = ET.fromstring(res.content)
        manchetes = []
        for item in root.findall(".//item")[:5]:
            titulo = item.find("title").text
            manchetes.append(f"- {titulo}")
        return "\n".join(manchetes)
    except Exception:
        return "Não foi possível obter as notícias agora."


def ler_conteudo_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        res = requests.get(url, headers=headers, timeout=6)
        texto = re.sub(r"<(script|style).*?>.*?</\1>", "", res.text, flags=re.S | re.I)
        texto = re.sub(r"<.*?>", " ", texto)
        texto = re.sub(r"\s+", " ", texto).strip()
        return texto[:3500]
    except Exception as e:
        return f"Erro ao ler o link: {e}"


# ==========================================
# 7. TELEMETRIA DO PC, CLIMA E VISÃO (ECRÃ)
# ==========================================
def obter_contexto_sistema(contexto_vetorial=""):
    agora = datetime.now()
    data_hora = f"{NOMES_DIAS_PT[agora.weekday()].capitalize()}, {agora.strftime('%d/%m/%Y às %H:%M:%S')}"

    try:
        res_clima = requests.get("https://wttr.in/?format=%l:+%C,+%t+(Sensação+%f),+Vento+%w", timeout=2.5)
        clima = res_clima.text.strip() if res_clima.status_code == 200 else "Indisponível"
    except Exception:
        clima = "Offline"

    info_hw = f"{platform.system()} {platform.release()}"
    if TEM_PSUTIL:
        cpu = psutil.cpu_percent(interval=0.05)
        ram = psutil.virtual_memory().percent
        disco = psutil.disk_usage("/").percent
        bat = psutil.sensors_battery()
        bat_str = f", Bateria: {bat.percent}%" if bat else ""
        info_hw += f" | CPU: {cpu}% | RAM: {ram}% | Disco: {disco}%{bat_str}"

    utilizador = os.getenv("USERNAME") or os.getenv("USER") or "Rodrigo"
    nivel_perm = "Administrador (Acesso Total)" if eh_administrador() else "Utilizador Padrão (pode elevar via UAC)"
    mem_vet_str = contexto_vetorial if contexto_vetorial else "Sem registos relevantes na base vetorial."
    agenda_str = resumo_agenda_para_llm(limite=8)

    scripts_disp = []
    try:
        if os.path.isdir(PASTA_SCRIPTS):
            scripts_disp = sorted([f for f in os.listdir(PASTA_SCRIPTS) if f.endswith(".py")])
    except Exception:
        pass
    scripts_str = ", ".join(scripts_disp) if scripts_disp else "Nenhum script personalizado na pasta 'scripts'."

    return (
        f"És o Rubos, o assistente pessoal local do Rodrigo em Português de Portugal (PT-PT), com voz portuguesa ativa e controlo do Windows.\n"
        f"[Personalidade e Regras de Conversação]\n"
        f"- Responde SEMPRE em Português de Portugal natural, fluido, prestável e direto — como um colega inteligente a conversar.\n"
        f"- Quando a resposta for falada por voz, evita listas intermináveis ou símbolos desnecessários; sê claro e objetivo.\n"
        f"- As mensagens vêm frequentemente de ditado por voz e podem ter erros fonéticos (ex.: 'pão que horas' -> 'são que horas'). Deduze sempre a intenção real pelo contexto sem dizer 'não entendi'.\n"
        f"- Nunca finjas que executaste uma ação no PC (abrir/fechar apps, tocar música, ligar a alguém ou correr scripts) se o sistema não a executou antes deste passo.\n"
        f"[Dados Atuais do Sistema]\n"
        f"- Utilizador: {utilizador} | Permissões: {nivel_perm}\n"
        f"- Data e Hora: {data_hora}\n"
        f"- Localização e Clima: {clima}\n"
        f"- Computador: {info_hw} | Apps indexadas: {len(apps_indexadas)}\n"
        f"- Scripts disponíveis em 'scripts': {scripts_str}\n"
        f"[Agenda do Utilizador (Próximos Eventos)]\n{agenda_str}\n"
        f"[Base de Dados Vetorial Privada (Conhecimento Guardado)]\n{mem_vet_str}\n"
    )


def capturar_ecra_b64():
    if TEM_PIL:
        img = ImageGrab.grab().convert("RGB")
        img.thumbnail((1024, 1024))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    else:
        temp_img = os.path.join(PASTA_ATUAL, "_temp_screen.jpg")
        ps = (
            f"Add-Type -AssemblyName System.Windows.Forms,System.Drawing; "
            f"$s = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds; "
            f"$b = New-Object System.Drawing.Bitmap($s.Width, $s.Height); "
            f"$g = [System.Drawing.Graphics]::FromImage($b); "
            f"$g.CopyFromScreen($s.Location, [System.Drawing.Point]::Empty, $s.Size); "
            f"$b.Save('{temp_img}', [System.Drawing.Imaging.ImageFormat]::Jpeg);"
        )
        subprocess.run(["powershell", "-WindowStyle", "Hidden", "-Command", ps], check=True, creationflags=FLAG_SEM_JANELA)
        with open(temp_img, "rb") as f:
            dados = base64.b64encode(f.read()).decode("ascii")
        if os.path.exists(temp_img):
            os.remove(temp_img)
        return dados


def preparar_imagem_ficheiro_b64(caminho):
    if TEM_PIL:
        img = Image.open(caminho).convert("RGB")
        img.thumbnail((1024, 1024))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    with open(caminho, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def modelo_suporta_visao(nome_modelo):
    return any(p in nome_modelo.lower() for p in PALAVRAS_VISAO)


def obter_modelo_visao_disponivel(modelo_atual):
    if modelo_suporta_visao(modelo_atual):
        return modelo_atual
    for m in modelos_instalados:
        if modelo_suporta_visao(m):
            return m
    return None


def analisar_imagem_ollama(modelo_visao, pergunta_utilizador, img_b64):
    garantir_ollama_ativo()
    prompt_direto = (
        f"Descreve objetivamente e em detalhe o que está visível nesta imagem ou captura de ecrã "
        f"(janelas abertas, texto, botões, ícones, cores e elementos gráficos). "
        f"Responde em Português de Portugal. Pergunta: {pergunta_utilizador}"
    )

    def _chamar_api(texto_prompt):
        res = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": modelo_visao,
                "messages": [{"role": "user", "content": texto_prompt, "images": [img_b64]}],
                "stream": False,
                "options": {"num_ctx": 4096, "temperature": 0.2}
            },
            timeout=120
        )
        res.raise_for_status()
        return res.json().get("message", {}).get("content", "").strip()

    resposta = _chamar_api(prompt_direto)
    frases_recusa = (
        "não posso fornecer ajuda", "não posso ajudar", "não consigo ajudar",
        "não posso analisar", "sorry", "cannot assist", "can't assist", "unable to"
    )
    if not resposta or any(f in resposta.lower() for f in frases_recusa):
        prompt_fallback = (
            f"List and describe objectively all visible software windows, text, UI elements, "
            f"icons, and objects shown in this computer screenshot. "
            f"Answer the user's question: '{pergunta_utilizador}'. "
            f"Write the entire response in European Portuguese."
        )
        resposta = _chamar_api(prompt_fallback)

    return resposta or "Não foi possível obter descrição da imagem."


# ==========================================
# 8. INTERPRETADOR DE COMANDOS DE SISTEMA, AGENDA E DIA A DIA
# ==========================================
def _executar_comando_unico(pergunta):
    p_strip = pergunta.strip()
    p_low = p_strip.lower()

    # 1. Guardar na Base de Dados Vetorial Privada
    match_mem = re.search(
        r"^(?:lembra-te que|guarda na mem[óo]ria:?|memoriza:?|guarda na base(?: de dados)?:?)\s+(.+)",
        p_strip,
        re.I
    )
    if match_mem:
        facto = match_mem.group(1).strip()
        adicionar_a_base_vetorial(facto, origem="Memória Pessoal")
        return True, f"Guardado na base de dados vetorial privada:\n\"{facto}\"", []

    if re.search(r"\b(?:apaga|limpa)\s+a\s+(?:mem[óo]ria|base\s+vetorial|base\s+de\s+dados)\b", p_low):
        limpar_base_vetorial()
        return True, "A base de dados vetorial privada foi limpa.", []

    # 1.5 AGENDA & CALENDÁRIO (Adicionar, Consultar, Remover)
    match_add_agenda = re.match(
        r"^(?:por\s+favor\s+)?(?:coloca|cria|adiciona|marca|agenda|regista|p[õo]e|mete)\s+"
        r"(?:um\s+)?(?:evento|compromisso|reuni[ãa]o|lembrete|aula|tarefa)(?:\s+(?:no\s+calend[áa]rio|na\s+agenda))?\s+(.+)$",
        p_strip,
        flags=re.I
    )
    if match_add_agenda:
        detalhe = match_add_agenda.group(1).strip().rstrip("?.!")
        resp_ag = adicionar_evento_agenda(detalhe)
        return True, resp_ag, [(FICHEIRO_AGENDA, "agenda_rubos.json")]

    match_lembra_hora = re.match(
        r"^(?:por\s+favor\s+)?lembra(?:-me)?\s+(?:de\s+)?(.+?\b(?:[àa]s\s+\d{1,2}(?:[:h]\d{2})?|amanh[ãa]|hoje|depois\s+de\s+amanh[ãa]|dia\s+\d{1,2})\b.*)$",
        p_strip,
        flags=re.I
    )
    if match_lembra_hora:
        detalhe = match_lembra_hora.group(1).strip().rstrip("?.!")
        resp_ag = adicionar_evento_agenda(detalhe)
        return True, resp_ag, [(FICHEIRO_AGENDA, "agenda_rubos.json")]

    if re.search(
        r"\b(?:o\s+que\s+(?:[ée]\s+que\s+)?tenho|quais\s+(?:s[ãa]o\s+)?os\s+(?:meus\s+)?eventos|"
        r"mostra(?:-me)?\s+(?:a\s+minha\s+)?(?:agenda|calend[áa]rio)|"
        r"ver\s+(?:a\s+minha\s+)?(?:agenda|calend[áa]rio)|"
        r"eventos?\s+(?:de\s+hoje|de\s+amanh[ãa]|marcados|agendados)|"
        r"tenho\s+algum\s+(?:evento|compromisso))\b",
        p_low
    ):
        if "amanhã" in p_low or "amanha" in p_low:
            return True, consultar_agenda_texto("amanha"), []
        if "hoje" in p_low:
            return True, consultar_agenda_texto("hoje"), []
        return True, consultar_agenda_texto("todos"), []

    match_del_agenda = re.match(
        r"^(?:por\s+favor\s+)?(?:apaga|remove|cancela|elimina|desmarca|limpa)\s+"
        r"(?:o\s+evento|o\s+compromisso|a\s+reuni[ãa]o|o\s+lembrete)?\s*(.+?)(?:\s+(?:da\s+agenda|do\s+calend[áa]rio))?$",
        p_strip,
        flags=re.I
    )
    if match_del_agenda and any(k in p_low for k in ("evento", "compromisso", "agenda", "calendário", "calendario", "desmarca")):
        alvo_ev = match_del_agenda.group(1).strip().rstrip("?.!")
        return True, remover_evento_agenda(alvo_ev), []

    # 1.6 TEMPORIZADOR / CONTAGEM DECRESCENTE
    match_timer = re.search(
        r"(?:temporizador|timer|conta(?:gem)?|avisa(?:-me)?\s+daqui\s+a)\s+(?:de\s+)?(\d+)\s*(segundos?|seg|minutos?|min|horas?|h)\b",
        p_low
    )
    if match_timer:
        qtd = int(match_timer.group(1))
        unid = match_timer.group(2)
        if unid.startswith("h"):
            segundos = qtd * 3600
            desc = f"{qtd} hora(s)"
        elif unid.startswith("m"):
            segundos = qtd * 60
            desc = f"{qtd} minuto(s)"
        else:
            segundos = qtd
            desc = f"{qtd} segundo(s)"

        def _disparar_timer(s_wait, d_txt):
            time.sleep(s_wait)
            msg_t = f"⏱️ Temporizador concluído ({d_txt})!"
            adicionar_ao_chat("Rubos", msg_t, "bot_tag")
            falar_com_piper(f"Rodrigo, terminou o temporizador de {d_txt}.")

        threading.Thread(target=_disparar_timer, args=(segundos, desc), daemon=True).start()
        return True, f"Temporizador iniciado para {desc}.", []

    # 2. Notas rápidas (Criar e Ler)
    if re.search(r"\b(?:l[êe]|mostra|abre|ver)\s+(?:as\s+)?(?:minhas\s+)?notas\b", p_low):
        if not os.path.exists(FICHEIRO_NOTAS):
            return True, "Ainda não tens nenhuma nota guardada.", []
        with open(FICHEIRO_NOTAS, "r", encoding="utf-8") as f:
            conteudo_n = f.read().strip()
        return True, f"As tuas notas:\n{conteudo_n}" if conteudo_n else "O ficheiro de notas está vazio.", [(FICHEIRO_NOTAS, "notas_rubos.txt")]

    match_nota = re.search(r"^(?:anota|cria uma nota|escreve uma nota):?\s+(.+)", p_strip, re.I)
    if match_nota:
        nota = match_nota.group(1).strip()
        with open(FICHEIRO_NOTAS, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%d/%m/%Y %H:%M')}] {nota}\n")
        adicionar_a_base_vetorial(nota, origem="Nota Rápida")
        return True, f"Nota guardada em '{FICHEIRO_NOTAS}' e indexada na base vetorial.", [(FICHEIRO_NOTAS, "notas_rubos.txt")]

    # 2.5 Controlo de Volume e Multimédia do Windows
    if re.search(r"\b(?:aumenta|sobe)\s+(?:o\s+)?volume\b", p_low):
        _enviar_tecla_media_windows(0xAF, repeticoes=5)
        return True, "Aumentei o volume do computador.", []

    if re.search(r"\b(?:baixa|diminui|reduz)\s+(?:o\s+)?volume\b", p_low):
        _enviar_tecla_media_windows(0xAE, repeticoes=5)
        return True, "Baixei o volume do computador.", []

    if re.search(r"\b(?:silencia|muta|mute|tira\s+o\s+som|ativa\s+o\s+som|desmuta)\b", p_low):
        _enviar_tecla_media_windows(0xAD, repeticoes=1)
        return True, "Alternei o estado de silêncio do som.", []

    if re.search(r"\b(?:pr[óo]xima\s+m[úu]sica|passa\s+(?:a\s+)?m[úu]sica|avan[çc]a\s+faixa)\b", p_low):
        _enviar_tecla_media_windows(0xB0, repeticoes=1)
        return True, "Passei para a próxima faixa.", []

    if re.search(r"\b(?:m[úu]sica\s+anterior|volta\s+(?:a\s+)?m[úu]sica|faixa\s+anterior)\b", p_low):
        _enviar_tecla_media_windows(0xB1, repeticoes=1)
        return True, "Voltei à faixa anterior.", []

    # 2.6 Estado do PC / Bateria / Bloquear Ecrã
    if re.search(r"\b(?:bloqueia\s+(?:o\s+)?(?:ecr[ãa]|computador|pc|sess[ãa]o))\b", p_low):
        if os.name == "nt":
            ctypes.windll.user32.LockWorkStation()
            return True, "Bloqueei a sessão do Windows.", []

    if re.search(r"\b(?:estado\s+do\s+(?:pc|computador|sistema)|quanto\s+(?:tenho\s+de\s+)?(?:bateria|ram|cpu|mem[óo]ria))\b", p_low):
        if TEM_PSUTIL:
            cpu = psutil.cpu_percent(interval=0.1)
            ram = psutil.virtual_memory().percent
            disco = psutil.disk_usage("/").percent
            bat = psutil.sensors_battery()
            bat_str = f" | Bateria: {bat.percent}% ({'a carregar' if bat.power_plugged else 'na bateria'})" if bat else ""
            return True, f"Estado do sistema: CPU a {cpu}%, RAM a {ram}%, Disco a {disco}%{bat_str}.", []

    # 2.7 Calculadora rápida
    match_calc = re.match(r"^(?:quanto\s+[ée]|calcula)\s+([0-9+\-*/().,xX÷\s]+)\??$", p_strip, re.I)
    if match_calc:
        expr_raw = match_calc.group(1).strip()
        if any(op in expr_raw for op in ("+", "-", "*", "/", "x", "X", "÷")):
            try:
                val = _calcular_expressao_segura(expr_raw)
                val_fmt = int(val) if isinstance(val, float) and val.is_integer() else round(val, 4)
                return True, f"{expr_raw} = {val_fmt}", []
            except Exception:
                pass

    # 3. Listar janelas abertas
    if re.search(
        r"\b(?:que\s+janelas|quais\s+janelas|lista\s+(?:as\s+)?janelas|janelas\s+abertas|programas\s+abertos|aplica[çc][õo]es\s+abertas)\b",
        p_low
    ):
        janelas = listar_janelas_abertas()
        if not janelas:
            return True, "Não existem outras janelas visíveis abertas neste momento.", []
        linhas = [f"• {j['titulo']} ({j['processo'] or 'Janela'})" for j in janelas]
        return True, "Janelas atualmente abertas no teu ecrã:\n" + "\n".join(linhas), []

    # 4. Listar aplicações instaladas indexadas
    if re.search(
        r"\b(?:que\s+aplica[çc][õo]es|quais\s+aplica[çc][õo]es|lista\s+(?:as\s+)?aplica[çc][õo]es|programas\s+instalados)\b",
        p_low
    ):
        if not apps_indexadas:
            indexar_aplicacoes_windows()
        nomes = sorted(list({v["nome"] for v in apps_indexadas.values()}))
        amostra = "\n".join([f"• {n}" for n in nomes[:40]])
        extra = f"\n... e mais {len(nomes) - 40} aplicações." if len(nomes) > 40 else ""
        return True, f"Tenho acesso a {len(nomes)} aplicações no teu computador. Exemplos:\n{amostra}{extra}", []

    # 5. Controlar janelas: FECHAR / MINIMIZAR / MAXIMIZAR / FOCAR
    match_janela = re.match(
        r"^(?:por\s+favor\s+)?(for[çc]a\s+fechar|fecha|encerra|mata|minimiza|maximiza|foca(?:\s+no|\s+na|\s+em)?|mostra(?:\s+a\s+janela)?)\s+"
        r"(?:a\s+janela\s+(?:do|da|de)\s+|o\s+ficheiro\s+|a\s+pasta\s+|o\s+programa\s+|a\s+aplica[çc][ãa]o\s+|o\s+|a\s+|os\s+|as\s+)?(.+)$",
        p_strip,
        flags=re.I
    )
    if match_janela:
        verbo_raw = match_janela.group(1).lower()
        alvo = match_janela.group(2).strip().rstrip("?.!")

        if verbo_raw.startswith("mostra") and re.search(r"\b(?:imagens?|fotos?|fotografias?)\b", alvo, re.I):
            return False, "", []

        forcar = "forç" in verbo_raw or "forc" in verbo_raw or "mata" in verbo_raw
        if any(w in verbo_raw for w in ("fecha", "encerra", "mata")):
            acao = "fechar"
        elif "minimiza" in verbo_raw:
            acao = "minimizar"
        elif "maximiza" in verbo_raw:
            acao = "maximizar"
        else:
            acao = "focar"

        ok, msg = controlar_janela(alvo, acao=acao, forcar=forcar)
        if ok or acao in ("fechar", "minimizar", "maximizar"):
            return True, msg, []

    # 6. Pesquisa no YouTube
    match_yt = re.search(r"pesquisa no youtube(?: por)?\s+(.+)", p_low)
    if match_yt:
        termo = match_yt.group(1).strip()
        webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(termo)}")
        return True, f"Abri a pesquisa por '{termo}' no YouTube.", []

    # 6.5 Listar ou executar scripts Python personalizados da pasta 'scripts'
    if re.search(r"\b(?:lista|quais|que)\s+(?:os\s+)?scripts\b", p_low):
        disponiveis = [f for f in os.listdir(PASTA_SCRIPTS) if f.endswith(".py")]
        if not disponiveis:
            return True, f"A pasta '{PASTA_SCRIPTS}' ainda não tem nenhum ficheiro .py.", []
        lista_s = "\n".join([f"• {s}" for s in disponiveis])
        return True, f"Scripts personalizados disponíveis na pasta 'scripts':\n{lista_s}", []

    match_script = re.match(
        r"^(?:por\s+favor\s+)?(?:corre|executa|roda|lan[çc]a)\s+(?:o\s+)?(?:script\s+)?([^\s]+)(?:\s+(?:com\s+(?:os\s+)?argumentos?\s+)?(.+))?$",
        p_strip,
        flags=re.I
    )
    if match_script:
        nome_sc = match_script.group(1).strip().rstrip("?.!")
        args_sc = (match_script.group(2) or "").strip().rstrip("?.!")
        ok_sc, msg_sc = executar_script_personalizado(nome_sc, args_sc)
        if ok_sc or "script" in p_low.split():
            return True, msg_sc, []

    if p_low.endswith(".py"):
        nome_direto = os.path.basename(p_strip)
        if os.path.exists(os.path.join(PASTA_SCRIPTS, nome_direto)):
            _, msg_sc = executar_script_personalizado(nome_direto, "")
            return True, msg_sc, []

    # 6.6b Play / Pausa / Retomar no Spotify
    match_sp_media = re.match(
        r"^(?:por\s+favor\s+)?(?:(?:coloca|p[õo]e|mete)\s+(?:o\s+|a\s+)?|(?:tira|remove)\s+(?:a\s+)?|(?:d[áa]\s+)?)?"
        r"(pausa|pausar|para|parar|play|continua|continuar|retoma|retomar|despausa|despausar)"
        r"(?:\s+(?:a\s+m[úu]sica|a\s+faixa|isso|da\s+m[úu]sica|do\s+spotify))?(?:\s+(?:no|na|do)\s+spotify)?$",
        p_low
    )
    if match_sp_media:
        verbo_sp = match_sp_media.group(1)
        script_sp_ctrl = os.path.join(PASTA_SCRIPTS, "controlar_spotify.py")
        if os.path.exists(script_sp_ctrl):
            _, msg_sp = executar_script_personalizado("controlar_spotify.py", verbo_sp)
            return True, msg_sp, []
        _enviar_tecla_media_windows(0xB3, repeticoes=1)
        return True, "Enviei o comando Play/Pausa multimédia.", []

    # 6.6 Colocar música no Spotify
    match_spotify = re.match(
        r"^(?:por\s+favor\s+)?(?:coloca|toca|p[õo]e|mete)\s+(?:a\s+m[úu]sica\s+|a\s+faixa\s+)?(.+?)\s+(?:no|na)\s+spotify$",
        p_strip,
        flags=re.I
    )
    if match_spotify:
        musica = match_spotify.group(1).strip().rstrip("?.!")
        abrir_aplicacao_pc("spotify", como_admin=False)
        time.sleep(1.5)
        controlar_janela("spotify", acao="focar")
        script_sp = os.path.join(PASTA_SCRIPTS, "tocar_spotify.py")
        if os.path.exists(script_sp):
            _, msg_sp = executar_script_personalizado("tocar_spotify.py", musica)
            return True, msg_sp, []
        return True, f"Abri e foquei o Spotify para '{musica}'.", []

    # 6.7 Ligar a alguém no Discord
    match_discord = re.match(
        r"^(?:por\s+favor\s+)?liga\s+(?:ao|à|a|para\s+(?:o|a)?)\s+(.+?)(?:\s+no\s+discord)?$",
        p_strip,
        flags=re.I
    )
    if match_discord:
        contacto = match_discord.group(1).strip().rstrip("?.!")
        abrir_aplicacao_pc("discord", como_admin=False)
        time.sleep(1.5)
        controlar_janela("discord", acao="focar")
        script_dc = os.path.join(PASTA_SCRIPTS, "ligar_discord.py")
        if os.path.exists(script_dc):
            _, msg_dc = executar_script_personalizado("ligar_discord.py", contacto)
            return True, msg_dc, []
        return True, f"Abri e foquei o Discord para '{contacto}'.", []

    # 7. ABRIR aplicações, sites, ficheiros ou pastas
    match_abrir = re.match(
        r"^(?:por\s+favor\s+)?(?:abre|executa|inicia|lan[çc]a)\s+(.+)$",
        p_strip,
        flags=re.I
    )
    if match_abrir:
        resto = match_abrir.group(1).strip().rstrip("?.!")
        como_admin = bool(re.search(r"\bcomo\s+administrador\b|\bcom\s+permiss[õo]es\b", resto, re.I))
        resto = re.sub(
            r"\s+(?:como\s+administrador|com\s+permiss[õo]es(?:\s+de\s+administrador)?)$",
            "",
            resto,
            flags=re.I
        ).strip()

        sites_rapidos = {
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "gmail": "https://mail.google.com",
            "whatsapp": "https://web.whatsapp.com",
            "github": "https://github.com",
            "chatgpt": "https://chatgpt.com",
            "calendário": "https://calendar.google.com",
            "calendario": "https://calendar.google.com",
        }
        chave_site = re.sub(r"^(?:o|a)\s+", "", resto.lower()).strip()
        if chave_site in sites_rapidos:
            webbrowser.open(sites_rapidos[chave_site])
            return True, f"Abri {chave_site.capitalize()} no navegador.", []

        if re.match(r"^(?:a\s+)?pasta\s+(?:de\s+)?imagens$", resto, re.I):
            abrir_ficheiro_no_windows(PASTA_IMAGENS, como_admin=como_admin)
            return True, f"Abri a pasta de imagens: {PASTA_IMAGENS}", []
        if re.match(r"^(?:a\s+)?pasta\s+(?:de\s+)?scripts$", resto, re.I):
            abrir_ficheiro_no_windows(PASTA_SCRIPTS, como_admin=como_admin)
            return True, f"Abri a pasta de scripts: {PASTA_SCRIPTS}", []

        pediu_ficheiro = bool(re.match(r"^(?:o\s+ficheiro|a\s+pasta|o\s+documento)\s+", resto, re.I))
        nome_limpo = re.sub(
            r"^(?:o\s+ficheiro|a\s+pasta|o\s+documento|o\s+programa|a\s+aplica[çc][ãa]o|o|a)\s+",
            "",
            resto,
            flags=re.I
        ).strip()

        if not pediu_ficheiro:
            ok_app, msg_app = abrir_aplicacao_pc(nome_limpo, como_admin=como_admin)
            if ok_app:
                return True, msg_app, []

        ficheiros_encontrados = procurar_ficheiros_pc(nome_limpo, limite=5)
        if ficheiros_encontrados:
            principal = ficheiros_encontrados[0]
            abrir_ficheiro_no_windows(principal, como_admin=como_admin)
            links = [(c, os.path.basename(c)) for c in ficheiros_encontrados]
            extra_admin = " (com permissões de Administrador)" if como_admin else ""
            return True, f"Abri{extra_admin}: {principal}", links

        if pediu_ficheiro:
            ok_app, msg_app = abrir_aplicacao_pc(nome_limpo, como_admin=como_admin)
            if ok_app:
                return True, msg_app, []

        return True, f"Não encontrei nenhuma aplicação ou ficheiro com o nome '{nome_limpo}' no computador.", []

    # 8. Procurar ficheiros sem abrir automaticamente
    match_proc_fich = re.match(
        r"^(?:procura|encontra|localiza|onde\s+est[áa])\s+(?:o\s+ficheiro|a\s+pasta|o\s+documento)\s+(.+)$",
        p_strip,
        flags=re.I
    )
    if match_proc_fich:
        nome_f = match_proc_fich.group(1).strip().rstrip("?.!")
        encontrados = procurar_ficheiros_pc(nome_f, limite=6)
        if encontrados:
            links = [(c, os.path.basename(c)) for c in encontrados]
            lista_txt = "\n".join([f"• {c}" for c in encontrados])
            return True, f"Encontrei estes resultados para '{nome_f}':\n{lista_txt}", links
        return True, f"Não encontrei nenhum ficheiro ou pasta com '{nome_f}'.", []

    return False, "", []


def processar_comandos_sistema(pergunta):
    """
    Suporta comandos encadeados, múltiplos alvos, data/hora instantânea,
    agenda, temporizadores, scripts Python e correção fonética.
    """
    correcoes_voz = [
        (r"\bp[ãa]o\s+que\s+horas\b", "são que horas"),
        (r"\bdiscorde\b", "discord"),
        (r"\bespotifai\b|\bspotifai\b", "spotify"),
        (r"\bgu[úu]guel\b", "google"),
        (r"\biutube\b|\byoutub\b", "youtube"),
        (r"\banreal\b|\bunreal\s+indine\b", "unreal engine"),
        (r"\bescript\b|\bescrit\b", "script"),
    ]
    pergunta_corrigida = pergunta.strip()
    for padrao_errado, correto in correcoes_voz:
        pergunta_corrigida = re.sub(padrao_errado, correto, pergunta_corrigida, flags=re.I)

    # Horas atuais
    if re.search(r"\b(?:s[ãa]o\s+que\s+horas|que\s+horas\s+s[ãa]o|diz(?:-me)?\s+as\s+horas)\b", pergunta_corrigida, re.I):
        return True, f"São {datetime.now().strftime('%H:%M')}.", []

    # Dia e data atuais
    if re.search(r"\b(?:que\s+dia\s+[ée]\s+hoje|hoje\s+[ée]\s+que\s+dia|qual\s+[ée]\s+a\s+data|dia\s+da\s+semana)\b", pergunta_corrigida, re.I):
        agora = datetime.now()
        return True, f"Hoje é {NOMES_DIAS_PT[agora.weekday()]}, {agora.strftime('%d/%m/%Y')}.", []

    verbos_acao = (
        r"(?:for[çc]a\s+fechar|fecha|encerra|mata|minimiza|maximiza|foca|"
        r"corre|roda|abre|executa|inicia|lan[çc]a|anota|memoriza|guarda|"
        r"coloca|toca|p[õo]e|mete|liga|marca|agenda|adiciona|"
        r"pausa|pausar|para|parar|play|continua|continuar|retoma|retomar|despausa|despausar)"
    )

    padrao_verbos = rf"(?:\s*[,;]\s*|\s+(?:e\s+depois|depois|de\s+seguida|e)\s+)(?=(?:por\s+favor\s+)?{verbos_acao}\b)"
    partes_brutas = [p.strip() for p in re.split(padrao_verbos, pergunta_corrigida, flags=re.I) if p.strip()]

    comandos_finais = []
    for parte in partes_brutas:
        if re.search(r"\b(?:evento|compromisso|reuni[ãa]o|agenda|calend[áa]rio|lembrete)\b", parte, re.I):
            comandos_finais.append(parte)
            continue

        match_multi_alvo = re.match(
            rf"^((?:por\s+favor\s+)?{verbos_acao})\s+(.+)$",
            parte,
            flags=re.I
        )
        if match_multi_alvo:
            verbo_prefixo = match_multi_alvo.group(1).strip()
            resto_alvos = match_multi_alvo.group(2).strip()

            sub_alvos = [
                a.strip() for a in re.split(r"\s*,\s*|\s+e\s+", resto_alvos, flags=re.I)
                if a.strip()
            ]
            if len(sub_alvos) > 1:
                for alvo in sub_alvos:
                    alvo_limpo = re.sub(r"^(?:o|a|os|as)\s+", "", alvo.strip(), flags=re.I).strip()
                    comandos_finais.append(f"{verbo_prefixo} {alvo_limpo}")
                continue

        comandos_finais.append(parte)

    if len(comandos_finais) > 1:
        respostas = []
        links_totais = []
        executou_algum = False

        for cmd in comandos_finais:
            ok, msg, links = _executar_comando_unico(cmd)
            if ok:
                executou_algum = True
                respostas.append(msg)
                links_totais.extend(links)
                time.sleep(0.15)

        if executou_algum:
            return True, "\n".join(respostas), links_totais

    return _executar_comando_unico(pergunta_corrigida)


# ==========================================
# 9. GESTÃO DE DISPOSITIVOS DE ÁUDIO E VOZ PORTUGUESA (PT-PT)
# ==========================================
def listar_dispositivos_audio():
    global mapa_dispositivos_entrada, mapa_dispositivos_saida
    entradas = {"Padrão do Sistema": None}
    saidas = {"Padrão do Sistema": None}

    if not TEM_SD:
        mapa_dispositivos_entrada = entradas
        mapa_dispositivos_saida = saidas
        return entradas, saidas

    try:
        try:
            sd._terminate()
            sd._initialize()
        except Exception:
            pass

        dispositivos = sd.query_devices()
        hostapis = sd.query_hostapis()

        for idx, dev in enumerate(dispositivos):
            nome_raw = dev.get("name", f"Dispositivo {idx}").strip()
            api_idx = dev.get("hostapi", 0)
            api_nome = hostapis[api_idx]["name"] if api_idx < len(hostapis) else ""

            if api_nome and not any(k in api_nome for k in ("MME", "DirectSound", "WASAPI")):
                continue

            if any(ign in nome_raw.lower() for ign in ("microsoft sound mapper", "driver primário", "primary sound")):
                continue

            curto_api = "WASAPI" if "WASAPI" in api_nome else ("DS" if "DirectSound" in api_nome else "MME")
            etiqueta = f"[{idx}] {nome_raw[:34]} ({curto_api})"

            if dev.get("max_input_channels", 0) > 0:
                entradas[etiqueta] = idx
            if dev.get("max_output_channels", 0) > 0:
                saidas[etiqueta] = idx
    except Exception:
        pass

    mapa_dispositivos_entrada = entradas
    mapa_dispositivos_saida = saidas
    return entradas, saidas


def obter_indice_entrada_selecionado():
    try:
        return mapa_dispositivos_entrada.get(var_dispositivo_entrada.get(), None)
    except Exception:
        return None


def obter_indice_saida_selecionado():
    try:
        return mapa_dispositivos_saida.get(var_dispositivo_saida.get(), None)
    except Exception:
        return None


def _encontrar_piper_exe():
    candidatos = [
        os.path.join(PASTA_VOZES_PIPER, "piper", "piper.exe"),
        os.path.join(PASTA_VOZES_PIPER, "piper.exe"),
    ]
    for c in candidatos:
        if os.path.exists(c):
            return c
    if os.path.isdir(PASTA_VOZES_PIPER):
        for raiz, _, ficheiros in os.walk(PASTA_VOZES_PIPER):
            if "piper.exe" in ficheiros:
                return os.path.join(raiz, "piper.exe")
    return ""


def _encontrar_modelo_piper_pt():
    """Procura qualquer modelo .onnx português dentro de vozes_piper (priorizando pt_PT / tugao)."""
    if os.path.exists(MODELO_PIPER_PADRAO) and os.path.getsize(MODELO_PIPER_PADRAO) > 1024:
        return MODELO_PIPER_PADRAO

    modelos_encontrados = []
    if os.path.isdir(PASTA_VOZES_PIPER):
        for raiz, _, ficheiros in os.walk(PASTA_VOZES_PIPER):
            for f in ficheiros:
                if f.lower().endswith(".onnx"):
                    cam = os.path.join(raiz, f)
                    if os.path.getsize(cam) > 1024:
                        modelos_encontrados.append(cam)

    if not modelos_encontrados:
        return ""

    for m in modelos_encontrados:
        nome = os.path.basename(m).lower()
        if "pt_pt" in nome or "pt-pt" in nome or "tugao" in nome:
            return m
    for m in modelos_encontrados:
        nome = os.path.basename(m).lower()
        if nome.startswith("pt_") or nome.startswith("pt-"):
            return m
    return modelos_encontrados[0]


PIPER_EXE = _encontrar_piper_exe()
MODELO_PIPER_ONNX = _encontrar_modelo_piper_pt()


def parar_voz_piper():
    global _stream_saida_ativo
    _parar_audio_tts.set()
    with _lock_saida_audio:
        if _stream_saida_ativo is not None:
            try:
                _stream_saida_ativo.stop()
                _stream_saida_ativo.close()
            except Exception:
                pass
            _stream_saida_ativo = None
    if os.name == "nt":
        try:
            winsound.PlaySound(None, winsound.SND_PURGE)
        except Exception:
            pass
        try:
            ctypes.windll.winmm.mciSendStringW("close rubos_tts", None, 0, None)
        except Exception:
            pass
    _tts_a_falar.clear()


def _reproduzir_wav_no_dispositivo(caminho_wav):
    global _stream_saida_ativo
    if _parar_audio_tts.is_set() or not os.path.exists(caminho_wav) or os.path.getsize(caminho_wav) < 100:
        return False

    dev_saida = obter_indice_saida_selecionado()
    if TEM_SD:
        try:
            with wave.open(caminho_wav, "rb") as wf:
                taxa = wf.getframerate()
                canais = wf.getnchannels()
                dados_raw = wf.readframes(wf.getnframes())

            audio_np = np.frombuffer(dados_raw, dtype=np.int16)
            if canais > 1:
                audio_np = audio_np.reshape(-1, canais)

            stream_out = sd.OutputStream(
                samplerate=taxa,
                channels=canais,
                dtype="int16",
                device=dev_saida
            )
            with _lock_saida_audio:
                _stream_saida_ativo = stream_out

            stream_out.start()
            bloco = 2048
            for pos in range(0, len(audio_np), bloco):
                if _parar_audio_tts.is_set():
                    break
                fatia = audio_np[pos:pos + bloco]
                if fatia.ndim == 1:
                    fatia = fatia.reshape(-1, 1)
                stream_out.write(fatia)

            with _lock_saida_audio:
                if _stream_saida_ativo is stream_out:
                    try:
                        stream_out.stop()
                        stream_out.close()
                    except Exception:
                        pass
                    _stream_saida_ativo = None
            return True
        except Exception:
            pass

    if os.name == "nt" and not _parar_audio_tts.is_set():
        try:
            winsound.PlaySound(caminho_wav, winsound.SND_FILENAME)
            return True
        except Exception:
            pass
    return False


def _falar_sapi_portugues(texto_limpo):
    """
    Usa exclusivamente uma voz Portuguesa (pt-PT ou pt-BR) instalada no Windows.
    Nunca utiliza vozes inglesas (David/Zira) para ler português.
    """
    if os.name != "nt" or not texto_limpo:
        return False

    caminho_wav = os.path.join(PASTA_VOZES_PIPER, f"_win_pt_{int(time.time() * 1000)}.wav")
    seguro = texto_limpo.replace("'", " ").replace('"', " ").replace("\n", " ")[:1200]

    ps = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$vozes = $s.GetInstalledVoices() | Where-Object { $_.Enabled }; "
        "$ptPT = $vozes | Where-Object { $_.VoiceInfo.Culture.Name -eq 'pt-PT' -or $_.VoiceInfo.Name -match 'Helia|Cristiano|Portugal' } | Select-Object -First 1; "
        "$ptAny = $vozes | Where-Object { $_.VoiceInfo.Culture.Name -like 'pt*' -or $_.VoiceInfo.Name -match 'Portugu|Maria|Daniel' } | Select-Object -First 1; "
        "$escolhida = if ($ptPT) { $ptPT } else { $ptAny }; "
        "if (-not $escolhida) { exit 2 }; "
        "$s.SelectVoice($escolhida.VoiceInfo.Name); "
        "$s.Rate = 1; "
        f"$s.SetOutputToWaveFile('{caminho_wav}'); "
        f"$s.Speak('{seguro}'); "
        "$s.SetOutputToNull(); "
        "$s.Dispose();"
    )

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps],
            capture_output=True, text=True, timeout=20, creationflags=FLAG_SEM_JANELA
        )
        if res.returncode == 0 and os.path.exists(caminho_wav) and os.path.getsize(caminho_wav) > 200:
            ok = _reproduzir_wav_no_dispositivo(caminho_wav)
            try:
                os.remove(caminho_wav)
            except Exception:
                pass
            return ok
    except Exception:
        pass
    finally:
        if os.path.exists(caminho_wav):
            try:
                os.remove(caminho_wav)
            except Exception:
                pass
    return False


def _falar_edge_neural_pt(texto_limpo, voz_edge="pt-PT-DuarteNeural"):
    """
    Sintetiza voz neural natural em Português de Portugal (pt-PT-DuarteNeural ou pt-PT-RaquelNeural)
    e reproduz via MCI nativo do Windows sem depender de vozes inglesas do sistema.
    """
    global TEM_EDGE_TTS, edge_tts
    if not TEM_EDGE_TTS:
        try:
            import importlib
            edge_tts = importlib.import_module("edge_tts")
            TEM_EDGE_TTS = True
        except ImportError:
            return False

    caminho_mp3 = os.path.join(PASTA_VOZES_PIPER, f"_edge_pt_{int(time.time() * 1000)}.mp3")
    try:
        async def _gerar():
            com = edge_tts.Communicate(texto_limpo, voz_edge)
            await com.save(caminho_mp3)

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_gerar())
        finally:
            loop.close()

        if _parar_audio_tts.is_set() or not os.path.exists(caminho_mp3) or os.path.getsize(caminho_mp3) < 200:
            return False

        if os.name == "nt":
            winmm = ctypes.windll.winmm
            winmm.mciSendStringW("close rubos_tts", None, 0, None)
            err = winmm.mciSendStringW(f'open "{caminho_mp3}" type mpegvideo alias rubos_tts', None, 0, None)
            if err != 0:
                return False
            winmm.mciSendStringW("play rubos_tts", None, 0, None)

            status_buf = ctypes.create_unicode_buffer(64)
            while not _parar_audio_tts.is_set():
                winmm.mciSendStringW("status rubos_tts mode", status_buf, 64, None)
                if status_buf.value.strip().lower() != "playing":
                    break
                time.sleep(0.08)

            winmm.mciSendStringW("close rubos_tts", None, 0, None)
            return True
    except Exception:
        return False
    finally:
        if os.path.exists(caminho_mp3):
            try:
                os.remove(caminho_mp3)
            except Exception:
                pass
    return False


def _falar_piper_local(texto_limpo):
    global PIPER_EXE, MODELO_PIPER_ONNX
    if not PIPER_EXE or not os.path.exists(PIPER_EXE):
        PIPER_EXE = _encontrar_piper_exe()
    if not MODELO_PIPER_ONNX or not os.path.exists(MODELO_PIPER_ONNX):
        MODELO_PIPER_ONNX = _encontrar_modelo_piper_pt()

    if not (PIPER_EXE and os.path.exists(PIPER_EXE) and MODELO_PIPER_ONNX and os.path.exists(MODELO_PIPER_ONNX)):
        return False

    caminho_wav = os.path.join(PASTA_VOZES_PIPER, f"_fala_{int(time.time() * 1000)}.wav")
    config_json = MODELO_PIPER_ONNX + ".json"

    for f_antigo in os.listdir(PASTA_VOZES_PIPER):
        if f_antigo.startswith("_fala_") and f_antigo.endswith(".wav"):
            try:
                os.remove(os.path.join(PASTA_VOZES_PIPER, f_antigo))
            except Exception:
                pass

    cmd_piper = [
        PIPER_EXE,
        "--model", os.path.abspath(MODELO_PIPER_ONNX),
        "--output_file", os.path.abspath(caminho_wav)
    ]
    if os.path.exists(config_json):
        cmd_piper.extend(["--config", os.path.abspath(config_json)])

    env_utf8 = os.environ.copy()
    env_utf8["PYTHONIOENCODING"] = "utf-8"

    try:
        subprocess.run(
            cmd_piper,
            cwd=os.path.dirname(PIPER_EXE),
            input=(texto_limpo + "\n").encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env_utf8,
            timeout=25,
            creationflags=FLAG_SEM_JANELA
        )
        if _parar_audio_tts.is_set():
            return True
        return _reproduzir_wav_no_dispositivo(caminho_wav)
    except Exception:
        return False


def falar_com_piper(texto, esperar_fim=False):
    """Sintetiza e reproduz a resposta exclusivamente com voz Portuguesa (PT-PT)."""
    global _aviso_voz_pt_mostrado
    if not voz_ativa:
        return

    texto_limpo = re.sub(r"```[\s\S]*?```", ". Consulta o código no ecrã. ", texto)
    texto_limpo = re.sub(r"[*#_~>|•↗`✅⏰⏱️🧠🎙️🔊🔇📄📁🌐🗣️]+", " ", texto_limpo)
    texto_limpo = re.sub(r"https?://\S+", "ligação", texto_limpo)
    texto_limpo = re.sub(r"\s+", " ", texto_limpo).strip()[:1500]
    if not texto_limpo:
        return

    modo_voz = "Automática (PT-PT)"
    try:
        modo_voz = var_motor_voz.get()
    except Exception:
        pass

    parar_voz_piper()
    _parar_audio_tts.clear()
    _tts_a_falar.set()

    def _tarefa_tts():
        global _aviso_voz_pt_mostrado
        try:
            falou = False
            if modo_voz == "Piper Local (PT-PT)":
                falou = _falar_piper_local(texto_limpo)
            elif modo_voz == "Windows Nativa (PT-PT)":
                falou = _falar_sapi_portugues(texto_limpo)
            elif modo_voz == "Neural Online (Raquel PT-PT)":
                falou = _falar_edge_neural_pt(texto_limpo, "pt-PT-RaquelNeural") or _falar_sapi_portugues(texto_limpo)
            elif modo_voz == "Neural Online (Duarte PT-PT)":
                falou = _falar_edge_neural_pt(texto_limpo, "pt-PT-DuarteNeural") or _falar_sapi_portugues(texto_limpo)
            else:
                falou = (
                    _falar_piper_local(texto_limpo)
                    or _falar_edge_neural_pt(texto_limpo, "pt-PT-DuarteNeural")
                    or _falar_sapi_portugues(texto_limpo)
                )

            if not falou and not _parar_audio_tts.is_set() and not _aviso_voz_pt_mostrado:
                _aviso_voz_pt_mostrado = True
                adicionar_ao_chat(
                    "Rubos",
                    "⚠️ Nenhuma voz em Português (PT-PT) está ativa no sistema.\n"
                    "Para teres voz portuguesa natural, executa no terminal: pip install edge-tts\n"
                    "Ou coloca o ficheiro 'pt_PT-tugao-medium.onnx' na pasta 'vozes_piper' (ou instala o pacote de voz Português de Portugal nas Definições do Windows).",
                    "bot_tag"
                )
        except Exception as e:
            atualizar_estado(f"⚠️ Falha na saída de som: {e}")
        finally:
            _tts_a_falar.clear()
            if gestor_voz.ativo and not ia_a_responder:
                atualizar_estado("🎙️ Em chamada — a ouvir...")

    t = threading.Thread(target=_tarefa_tts, daemon=True)
    t.start()
    if esperar_fim:
        t.join(timeout=8.0)


# ==========================================
# 10. GESTOR DE CHAMADA POR VOZ CONTÍNUA (STT PT-PT)
# ==========================================
class _StreamFilaBytes:
    def __init__(self, fila_audio, parar_evt):
        self._fila = fila_audio
        self._parar = parar_evt
        self._sobra = bytearray()

    def limpar(self):
        self._sobra.clear()
        while not self._fila.empty():
            try:
                self._fila.get_nowait()
            except queue.Empty:
                break

    def read(self, size):
        while len(self._sobra) < size and not self._parar.is_set():
            try:
                bloco = self._fila.get(timeout=0.3)
                self._sobra.extend(bloco)
            except queue.Empty:
                continue
        if len(self._sobra) >= size:
            saida = bytes(self._sobra[:size])
            del self._sobra[:size]
            return saida
        saida = bytes(self._sobra)
        self._sobra.clear()
        return saida


class MicrofoneSoundDevice(sr.AudioSource if TEM_SR else object):
    def __init__(self, device_index=None, sample_rate=16000, chunk_size=1024):
        self.device_index = device_index
        self.SAMPLE_RATE = sample_rate
        self.CHUNK = chunk_size
        self.SAMPLE_WIDTH = 2
        self._raw_stream = None
        self.stream = None
        self._fila = queue.Queue(maxsize=200)
        self._parar_evt = threading.Event()
        self._taxa_nativa = sample_rate

    def limpar_buffer(self):
        if self.stream is not None:
            self.stream.limpar()

    def __enter__(self):
        self._parar_evt.clear()
        while not self._fila.empty():
            try:
                self._fila.get_nowait()
            except queue.Empty:
                break

        try:
            info_dev = sd.query_devices(self.device_index, "input")
            taxa_disp = int(info_dev.get("default_samplerate", 16000))
        except Exception:
            taxa_disp = 16000

        taxas_tentar = [16000] if taxa_disp == 16000 else [16000, taxa_disp]
        ultimo_erro = None

        for taxa in taxas_tentar:
            try:
                self._taxa_nativa = taxa
                self.SAMPLE_RATE = 16000

                def _callback_audio(indata, frames, time_info, status):
                    if self._parar_evt.is_set():
                        return
                    dados = np.frombuffer(indata, dtype=np.int16)
                    if self._taxa_nativa != 16000 and len(dados) > 0:
                        fator = 16000.0 / float(self._taxa_nativa)
                        novo_tam = max(1, int(round(len(dados) * fator)))
                        indices = np.linspace(0, len(dados) - 1, novo_tam)
                        dados = np.interp(indices, np.arange(len(dados)), dados).astype(np.int16)
                    try:
                        self._fila.put_nowait(dados.tobytes())
                    except queue.Full:
                        try:
                            self._fila.get_nowait()
                            self._fila.put_nowait(dados.tobytes())
                        except Exception:
                            pass

                self._raw_stream = sd.RawInputStream(
                    samplerate=taxa,
                    blocksize=self.CHUNK,
                    dtype="int16",
                    channels=1,
                    device=self.device_index,
                    callback=_callback_audio
                )
                self._raw_stream.start()
                self.stream = _StreamFilaBytes(self._fila, self._parar_evt)
                return self
            except Exception as err:
                ultimo_erro = err
                if self._raw_stream is not None:
                    try:
                        self._raw_stream.close()
                    except Exception:
                        pass
                    self._raw_stream = None

        raise ultimo_erro if ultimo_erro else RuntimeError("Não foi possível abrir o dispositivo de entrada.")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._parar_evt.set()
        if self._raw_stream is not None:
            try:
                self._raw_stream.stop()
                self._raw_stream.close()
            except Exception:
                pass
            self._raw_stream = None
            self.stream = None


class GestorChamadaVoz:
    def __init__(self):
        self.ativo = False
        self.reiniciar_stream = False
        self.lock = threading.Lock()
        self.temporizador = None
        self.recognizer = sr.Recognizer() if TEM_SR else None
        self._configurar_recognizer()

    def _configurar_recognizer(self):
        if self.recognizer:
            self.recognizer.dynamic_energy_threshold = False
            self.recognizer.energy_threshold = 60
            self.recognizer.pause_threshold = 0.95
            self.recognizer.non_speaking_duration = 0.4

    def alternar(self):
        global TEM_SR, sr
        if not TEM_SR:
            try:
                import importlib
                sr = importlib.import_module("speech_recognition")
                TEM_SR = True
                self.recognizer = sr.Recognizer()
                self._configurar_recognizer()
            except ImportError:
                messagebox.showwarning(
                    "Reconhecimento de Voz",
                    "Falta instalar as bibliotecas de microfone.\n"
                    "Executa no terminal: pip install SpeechRecognition sounddevice numpy"
                )
                return

        if not TEM_SD:
            messagebox.showwarning(
                "Reconhecimento de Voz",
                "Falta instalar o módulo sounddevice.\n"
                "Executa no terminal: pip install sounddevice numpy"
            )
            return

        with self.lock:
            self.ativo = not self.ativo
            estado_novo = self.ativo

        self._atualizar_botoes_ui(estado_novo)

        if estado_novo:
            self._configurar_recognizer()
            atualizar_estado("🎙️ A ligar microfone selecionado...")
            threading.Thread(target=self._ciclo_escuta, daemon=True).start()
        else:
            self._cancelar_temporizador()
            parar_voz_piper()
            atualizar_estado("🟢 Pronto")

    def trocar_microfone_em_curso(self):
        if self.ativo:
            self.reiniciar_stream = True
            atualizar_estado("🔄 A mudar de microfone...")

    def parar_silenciosamente(self):
        with self.lock:
            self.ativo = False
        self._cancelar_temporizador()
        parar_voz_piper()

    def _cancelar_temporizador(self):
        with self.lock:
            if self.temporizador is not None:
                self.temporizador.cancel()
                self.temporizador = None

    def _atualizar_botoes_ui(self, em_chamada):
        def _ui():
            if em_chamada:
                btn_chamada_side.configurar_visual(
                    texto="🔴  Terminar Chamada",
                    bg_cor="#2b1620",
                    hover_cor="#3b1d2b",
                    click_cor="#4f2539",
                    fg_cor=ACCENT_ROSE,
                    border_cor="#be123c"
                )
            else:
                btn_chamada_side.configurar_visual(
                    texto="🎙️  Chamada Voz: OFF",
                    bg_cor="#132e26",
                    hover_cor="#193d32",
                    click_cor="#214f41",
                    fg_cor=ACCENT_GREEN,
                    border_cor="#059669"
                )
        janela.after(0, _ui)

    def _ciclo_escuta(self):
        while self.ativo:
            self.reiniciar_stream = False
            dev_entrada = obter_indice_entrada_selecionado()
            try:
                with MicrofoneSoundDevice(device_index=dev_entrada) as fonte:
                    if self.ativo:
                        atualizar_estado("🎙️ Em chamada — podes falar agora...")

                    while self.ativo and not self.reiniciar_stream:
                        # Aguarda o Rubos terminar de pensar e responder por voz para evitar eco,
                        # retomando imediatamente a escuta contínua assim que ele termina de falar.
                        if ia_a_responder or _tts_a_falar.is_set():
                            while self.ativo and not self.reiniciar_stream and (ia_a_responder or _tts_a_falar.is_set()):
                                time.sleep(0.1)
                            time.sleep(0.25)
                            fonte.limpar_buffer()
                            if self.ativo and not self.reiniciar_stream:
                                atualizar_estado("🎙️ Em chamada — a ouvir...")
                            continue

                        try:
                            audio = self.recognizer.listen(fonte, timeout=1.0, phrase_time_limit=18)
                            if not self.ativo or self.reiniciar_stream:
                                break
                            if ia_a_responder or _tts_a_falar.is_set():
                                continue
                            atualizar_estado("📝 A transcrever...")
                            texto_ouvido = self.recognizer.recognize_google(audio, language="pt-PT").strip()
                            if texto_ouvido and self.ativo and not ia_a_responder and not _tts_a_falar.is_set():
                                self._ao_reconhecer_fala(texto_ouvido)
                        except sr.WaitTimeoutError:
                            continue
                        except sr.UnknownValueError:
                            if self.ativo and not ia_a_responder and not _tts_a_falar.is_set() and not self.reiniciar_stream:
                                atualizar_estado("🎙️ Em chamada — a ouvir...")
                            continue
                        except sr.RequestError:
                            if self.ativo:
                                atualizar_estado("⚠️ Sem ligação à internet para transcrever voz")
                                time.sleep(1.5)
                        except Exception as e:
                            if self.ativo:
                                atualizar_estado(f"⚠️ Erro no áudio ({str(e)[:45]}) — a tentar novamente...")
                                time.sleep(0.8)
            except Exception as e:
                with self.lock:
                    self.ativo = False
                self._atualizar_botoes_ui(False)
                atualizar_estado("⚠️ Microfone indisponível")
                janela.after(0, lambda err=e: messagebox.showerror(
                    "Erro de Microfone",
                    f"Não foi possível aceder ao microfone selecionado:\n{err}"
                ))
                break

    def _ao_reconhecer_fala(self, novo_trecho):
        self._cancelar_temporizador()

        def _atualizar_caixa_e_timer():
            texto_na_caixa = caixa_entrada.get().strip()
            texto_combinado = f"{texto_na_caixa} {novo_trecho}".strip() if texto_na_caixa else novo_trecho

            caixa_entrada.delete(0, tk.END)
            caixa_entrada.insert(0, texto_combinado)
            caixa_entrada.icursor(tk.END)
            btn_enviar.set_disabled(False)

            atualizar_estado("⏳ A aguardar 2.0s de silêncio para responder...")

            with self.lock:
                if self.ativo:
                    self.temporizador = threading.Timer(2.0, self._disparar_envio_automatico)
                    self.temporizador.daemon = True
                    self.temporizador.start()

        janela.after(0, _atualizar_caixa_e_timer)

    def _disparar_envio_automatico(self):
        def _enviar():
            global ultimo_prompt_enviado_voz
            if not self.ativo:
                return
            conteudo = caixa_entrada.get().strip()
            if conteudo:
                ultimo_prompt_enviado_voz = conteudo
                enviar_mensagem(via_voz=True)
        janela.after(0, _enviar)


gestor_voz = GestorChamadaVoz()


# ==========================================
# 11. EXIBIÇÃO NO CHAT E FLUXO PRINCIPAL
# ==========================================
def atualizar_estado(texto):
    try:
        janela.after(0, lambda: lbl_estado.config(text=texto))
    except Exception:
        pass


def adicionar_ao_chat(remetente, texto, tag=None, ficheiros_img=None, termo_google=None, mostrar_pasta=False):
    def _inserir():
        sz_link = max(8, tamanho_fonte_atual["btn"])
        hora_msg = datetime.now().strftime("%H:%M")

        area_chat.config(state=tk.NORMAL)
        area_chat.insert(tk.END, f"{remetente.upper()}  ", tag if tag else "")
        area_chat.insert(tk.END, f"{hora_msg}\n", "time_tag")
        area_chat.insert(tk.END, f"{texto}\n", "body_tag")

        if ficheiros_img:
            for idx, (caminho, titulo) in enumerate(ficheiros_img, 1):
                nome_fich = os.path.basename(caminho)
                tag_f = f"file_{idx}_{int(time.time() * 1000)}"
                area_chat.insert(tk.END, f"  📄 Abrir: {nome_fich} ({caminho}) ↗\n", tag_f)
                area_chat.tag_config(tag_f, foreground=ACCENT_GREEN, underline=True, font=("Segoe UI Semibold", sz_link))
                area_chat.tag_bind(tag_f, "<Button-1>", lambda e, p=caminho: abrir_ficheiro_no_windows(p))
                area_chat.tag_bind(tag_f, "<Enter>", lambda e: area_chat.config(cursor="hand2"))
                area_chat.tag_bind(tag_f, "<Leave>", lambda e: area_chat.config(cursor=""))

        if mostrar_pasta:
            tag_pasta = f"folder_{int(time.time() * 1000)}"
            area_chat.insert(tk.END, f"  📁 Abrir pasta de imagens: {PASTA_IMAGENS} ↗\n", tag_pasta)
            area_chat.tag_config(tag_pasta, foreground=ACCENT_AMBER, underline=True, font=("Segoe UI Semibold", sz_link))
            area_chat.tag_bind(tag_pasta, "<Button-1>", lambda e: abrir_ficheiro_no_windows(PASTA_IMAGENS))
            area_chat.tag_bind(tag_pasta, "<Enter>", lambda e: area_chat.config(cursor="hand2"))
            area_chat.tag_bind(tag_pasta, "<Leave>", lambda e: area_chat.config(cursor=""))

        if termo_google:
            url_g = f"https://www.google.com/search?tbm=isch&q={urllib.parse.quote(termo_google)}"
            tag_link = f"link_{int(time.time() * 1000)}"
            area_chat.insert(tk.END, f"  🌐 Ver '{termo_google}' no Google Imagens ↗\n", tag_link)
            area_chat.tag_config(tag_link, foreground=ACCENT_CYAN, underline=True, font=("Segoe UI Semibold", sz_link))
            area_chat.tag_bind(tag_link, "<Button-1>", lambda e, u=url_g: webbrowser.open(u))
            area_chat.tag_bind(tag_link, "<Enter>", lambda e: area_chat.config(cursor="hand2"))
            area_chat.tag_bind(tag_link, "<Leave>", lambda e: area_chat.config(cursor=""))

        area_chat.insert(tk.END, "\n", "spacer_tag")
        area_chat.config(state=tk.DISABLED)
        area_chat.see(tk.END)
    janela.after(0, _inserir)


def enviar_mensagem(forcar_web=False, forcar_imagens=False, via_voz=False, guardar_memoria=False):
    global imagem_anexada_b64, pedido_atual_id, ia_a_responder, ultimo_prompt_enviado_voz
    pergunta = caixa_entrada.get().strip()
    if not pergunta and not imagem_anexada_b64:
        return
    if not pergunta and imagem_anexada_b64:
        pergunta = "Analisa esta imagem/ecrã em detalhe e descreve o que vês."

    if not via_voz:
        ultimo_prompt_enviado_voz = pergunta

    parar_voz_piper()

    img_para_enviar = imagem_anexada_b64
    imagem_anexada_b64 = None
    lbl_anexo.config(text="")

    etiqueta_voz = "  [🎙️ Voz]" if via_voz else ""
    etiqueta_mem = "  [🧠 Pesquisar & Memorizar]" if guardar_memoria else ""
    etiqueta_img = "  [📷 Imagem anexada]" if img_para_enviar else ""
    adicionar_ao_chat("Tu", pergunta + etiqueta_voz + etiqueta_mem + etiqueta_img, "user_tag")

    caixa_entrada.delete(0, tk.END)
    btn_enviar.set_disabled(True)

    pedido_atual_id += 1
    id_deste_pedido = pedido_atual_id
    ia_a_responder = True

    threading.Thread(
        target=processar_pedido,
        args=(pergunta, img_para_enviar, forcar_web or guardar_memoria, forcar_imagens, id_deste_pedido, guardar_memoria),
        daemon=True
    ).start()


def _finalizar_turno_ia(id_pedido):
    global ia_a_responder, ultimo_prompt_enviado_voz
    if id_pedido == pedido_atual_id:
        ia_a_responder = False
        ultimo_prompt_enviado_voz = ""
        if gestor_voz.ativo:
            estado_final = "🗣️ A falar resposta..." if _tts_a_falar.is_set() else "🎙️ Em chamada — a ouvir..."
        else:
            estado_final = "🟢 Pronto"
        atualizar_estado(estado_final)
        janela.after(0, lambda: btn_enviar.set_disabled(False))


def _guardar_conhecimento_pesquisa(tema, texto_bruto_web, resposta_sintetizada):
    origem = f"Pesquisa Memorizada: {tema[:45]}"
    if resposta_sintetizada.strip():
        adicionar_a_base_vetorial(f"[{tema}] {resposta_sintetizada.strip()}", origem=origem)

    if texto_bruto_web and "Sem resultados relevantes" not in texto_bruto_web:
        linhas = [l.strip() for l in texto_bruto_web.splitlines() if l.strip()]
        for bloco in linhas[:8]:
            adicionar_a_base_vetorial(f"[{tema}] {bloco}", origem=origem)


def processar_pedido(pergunta, img_b64, forcar_web, forcar_imagens, id_pedido, guardar_memoria=False):
    global ultima_resposta_texto, historico_chat

    def _foi_cancelado():
        return id_pedido != pedido_atual_id

    modelo = var_modelo.get()
    contexto_extra = []
    ficheiros_encontrados = []
    termo_pesquisa_img = None
    resultados_web_brutos = ""
    p_low = pergunta.lower()

    # Caso A: Análise de imagem ou captura de ecrã
    if img_b64:
        modelo_visao = obter_modelo_visao_disponivel(modelo)
        if not modelo_visao:
            if not _foi_cancelado():
                msg_erro = (
                    "Nenhum modelo com visão está instalado no Ollama.\n"
                    "Executa no terminal: ollama pull minicpm-v"
                )
                adicionar_ao_chat("Rubos", msg_erro, "bot_tag")
                falar_com_piper(msg_erro)
                _finalizar_turno_ia(id_pedido)
            return

        atualizar_estado(f"👁️ {modelo_visao} a analisar o ecrã/imagem...")
        try:
            resposta_ia = analisar_imagem_ollama(modelo_visao, pergunta, img_b64)
        except Exception as e:
            resposta_ia = f"Erro de ligação ao Ollama: {e}"

        if _foi_cancelado():
            return

        if guardar_memoria:
            adicionar_a_base_vetorial(f"[Análise Visual: {pergunta}] {resposta_ia}", origem="Memória Visual")
            resposta_ia += "\n\n✅ Guardado na base de dados vetorial."

        historico_chat.append({"role": "user", "content": f"[Imagem enviada] {pergunta}"})
        historico_chat.append({"role": "assistant", "content": resposta_ia})
        ultima_resposta_texto = resposta_ia

        adicionar_ao_chat("Rubos", resposta_ia, "bot_tag")
        falar_com_piper(resposta_ia)
        _finalizar_turno_ia(id_pedido)
        return

    # Caso B: Comandos diretos de sistema, agenda, janelas, aplicações ou ficheiros
    if not forcar_web and not forcar_imagens and not guardar_memoria:
        executou_cmd, resp_cmd, links_cmd = processar_comandos_sistema(pergunta)
        if _foi_cancelado():
            return
        if executou_cmd:
            historico_chat.append({"role": "user", "content": pergunta})
            historico_chat.append({"role": "assistant", "content": resp_cmd})
            ultima_resposta_texto = resp_cmd
            adicionar_ao_chat("Rubos", resp_cmd, "bot_tag", ficheiros_img=links_cmd)
            falar_com_piper(resp_cmd)
            _finalizar_turno_ia(id_pedido)
            return

    # Caso C: Pergunta sobre onde as imagens foram guardadas
    perguntou_onde_guardou = bool(re.search(
        r"\b(?:onde|qual\s+(?:[ée]|a)\s+pasta|em\s+que\s+pasta|caminho|diret[óo]rio|localiza[çc][ãa]o)\b.*\b(?:imagens?|fotos?|guardad[ao]s?|guardaste|ficaram)\b",
        p_low
    ))
    if perguntou_onde_guardou and not guardar_memoria:
        if _foi_cancelado():
            return
        ultimas_imgs = listar_ultimas_imagens_guardadas(limite=5)
        resposta_local = f"As imagens descarregadas ficam guardadas em:\n{PASTA_IMAGENS}"
        ultima_resposta_texto = resposta_local
        adicionar_ao_chat("Rubos", resposta_local, "bot_tag", ficheiros_img=ultimas_imgs, mostrar_pasta=True)
        falar_com_piper("As imagens descarregadas ficam guardadas na pasta de imagens do Rubos.")
        _finalizar_turno_ia(id_pedido)
        return

    # Caso D: Pesquisa de imagens na web
    pediu_imagens = forcar_imagens or bool(re.search(
        r"\b(?:imagens?|fotos?|fotografias?|ilustra[çc][õo]es?|wallpapers?)\s+(?:de|do|da|dos|das|sobre)\b|"
        r"\b(?:mostra|manda|envia|pesquisa|procura|busca|quero\s+ver|encontra|traz|d[áa])(?:-me)?\b.*\b(?:imagens?|fotos?|fotografias?)\b",
        p_low
    ))
    if pediu_imagens and not guardar_memoria:
        atualizar_estado("🖼️ A descarregar e abrir imagens no Windows...")
        ficheiros_encontrados, termo_pesquisa_img, erro_img = pesquisar_e_abrir_imagens(pergunta, limite=3)
        if _foi_cancelado():
            return
        if ficheiros_encontrados:
            contexto_extra.append(
                f"[INSTRUÇÃO: Descarregaste {len(ficheiros_encontrados)} imagens de '{termo_pesquisa_img}' para '{PASTA_IMAGENS}' "
                f"e já as abriste no visualizador do Windows. Confirma numa frase curta sem usar formato ![...](...).]"
            )
        else:
            contexto_extra.append(
                f"[INSTRUÇÃO: {erro_img} Existe um link clicável em baixo para abrir '{termo_pesquisa_img}' no Google Imagens.]"
            )

    urls = re.findall(r"https?://\S+", pergunta)
    if urls:
        atualizar_estado("🌐 A ler página web...")
        conteudo_url = ler_conteudo_url(urls[0])
        resultados_web_brutos += "\n" + conteudo_url
        contexto_extra.append(f"[Conteúdo de {urls[0]}]\n{conteudo_url}")
        if _foi_cancelado():
            return

    if any(k in p_low for k in ["notícias", "noticias", "atualidade", "novidades no mundo"]):
        atualizar_estado("📰 A obter notícias...")
        noticias_txt = obter_noticias_atuais()
        resultados_web_brutos += "\n" + noticias_txt
        contexto_extra.append("[Últimas Notícias]\n" + noticias_txt)
    elif not pediu_imagens and (guardar_memoria or forcar_web or (auto_web_ativo and any(
        k in p_low for k in [
            "pesquisa", "procura", "internet", "web", "google", "quem é", "quem foi",
            "o que é", "onde fica", "quando", "preço", "cotação", "quanto custa",
            "resultado", "jogo", "2025", "2026", "atualmente", "hoje em dia"
        ]
    ))):
        atualizar_estado("🌐 A pesquisar na internet...")
        resultados_web_brutos = pesquisar_na_internet(pergunta)
        contexto_extra.append(f"[Resultados da Pesquisa na Internet]\n{resultados_web_brutos}")

    if _foi_cancelado():
        return

    if guardar_memoria:
        contexto_extra.append(
            "[INSTRUÇÃO ESPECIAL DE MEMORIZAÇÃO: O utilizador carregou no botão 'Guardar na Memória'. "
            "Faz uma síntese técnica completa, estruturada e detalhada sobre o tema pesquisado com todos os conceitos, "
            "factos, métodos e detalhes importantes para ficar registado na base de conhecimento permanente.]"
        )

    contexto_vet = pesquisar_base_vetorial(pergunta, top_k=4)

    atualizar_estado("🔄 A verificar ligação ao Ollama...")
    if not garantir_ollama_ativo(timeout_arranque=8.0):
        resposta_ia = (
            "Não consegui iniciar ou ligar ao Ollama na porta 11434.\n"
            "Abre a aplicação Ollama no Windows e tenta novamente."
        )
        adicionar_ao_chat("Rubos", resposta_ia, "bot_tag")
        falar_com_piper("Não consegui ligar ao Ollama. Abre o Ollama no Windows e tenta novamente.")
        _finalizar_turno_ia(id_pedido)
        return

    atualizar_estado(f"🧠 {modelo} a gerar resposta...")
    sistema_prompt = obter_contexto_sistema(contexto_vetorial=contexto_vet)
    if contexto_extra:
        sistema_prompt += "\n" + "\n\n".join(contexto_extra)

    mensagens_api = [{"role": "system", "content": sistema_prompt}]
    mensagens_api.extend(historico_chat[-8:])
    mensagens_api.append({"role": "user", "content": pergunta})

    try:
        res = requests.post(
            "http://localhost:11434/api/chat",
            json={
                "model": modelo,
                "messages": mensagens_api,
                "stream": False,
                "options": {"num_ctx": 4096}
            },
            timeout=120
        )
        res.raise_for_status()
        resposta_ia = res.json().get("message", {}).get("content", "Sem resposta do modelo.")
    except Exception as e:
        resposta_ia = f"Erro de ligação ao Ollama: {e}"

    if _foi_cancelado():
        return

    resposta_ia = re.sub(r"!\[.*?\]\(.*?\)", "", resposta_ia).strip()
    if not resposta_ia and ficheiros_encontrados:
        resposta_ia = f"Aqui estão as imagens de '{termo_pesquisa_img}', guardadas em {PASTA_IMAGENS}."

    if guardar_memoria:
        atualizar_estado("💾 A guardar conhecimento na base de dados vetorial...")
        _guardar_conhecimento_pesquisa(pergunta, resultados_web_brutos, resposta_ia)
        resposta_ia += "\n\n✅ Toda esta pesquisa foi guardada automaticamente na base de dados vetorial."

    historico_chat.append({"role": "user", "content": pergunta})
    historico_chat.append({"role": "assistant", "content": resposta_ia})
    ultima_resposta_texto = resposta_ia

    adicionar_ao_chat(
        "Rubos",
        resposta_ia,
        "bot_tag",
        ficheiros_img=ficheiros_encontrados,
        termo_google=termo_pesquisa_img,
        mostrar_pasta=bool(ficheiros_encontrados)
    )
    falar_com_piper(resposta_ia)
    _finalizar_turno_ia(id_pedido)


# ==========================================
# 12. COMPONENTE DE BOTÃO ARREDONDADO MODERNO (CANVAS)
# ==========================================
class BotaoArredondado(tk.Canvas):
    def __init__(
        self, pai, texto, comando,
        bg_cor=BG_ELEVATED,
        hover_cor="#2a3145",
        click_cor="#363f57",
        fg_cor=TEXT_PRIMARY,
        border_cor=BORDER_SUBTLE,
        hover_border_cor=BORDER_ACTIVE,
        raio=16,
        pad_x=16,
        pad_y=8,
        expand_x=False,
        alinhar="center",
        fonte=("Segoe UI Semibold", 9),
        bg_pai=None
    ):
        cor_fundo_pai = bg_pai if bg_pai else pai.cget("bg")
        super().__init__(pai, bg=cor_fundo_pai, highlightthickness=0, bd=0, cursor="hand2")

        self.texto = texto
        self.comando = comando
        self.bg_cor = bg_cor
        self.hover_cor = hover_cor
        self.click_cor = click_cor
        self.fg_cor = fg_cor
        self.border_cor = border_cor
        self.hover_border_cor = hover_border_cor
        self.raio = raio
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.expand_x = expand_x
        self.alinhar = alinhar
        self.fonte_obj = tkfont.Font(
            family=fonte[0],
            size=fonte[1],
            weight="bold" if "bold" in fonte[0].lower() or len(fonte) > 2 else "normal"
        )

        self._estado_atual = "normal"
        self._desabilitado = False
        self._offset_y = 0

        self._recalcular_dimensoes()

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", lambda e: self._desenhar())

    def _recalcular_dimensoes(self):
        largura_texto = self.fonte_obj.measure(self.texto)
        altura_texto = self.fonte_obj.metrics("linespace")
        altura_total = altura_texto + (self.pad_y * 2)
        self.config(height=altura_total)
        if not self.expand_x:
            largura_total = largura_texto + (self.pad_x * 2)
            self.config(width=largura_total)

    def _desenhar_forma_arredondada(self, x1, y1, x2, y2, r, cor):
        r = max(2, min(r, int((x2 - x1) / 2), int((y2 - y1) / 2)))
        self.create_oval(x1, y1, x1 + 2 * r, y1 + 2 * r, fill=cor, outline="")
        self.create_oval(x2 - 2 * r, y1, x2, y1 + 2 * r, fill=cor, outline="")
        self.create_oval(x1, y2 - 2 * r, x1 + 2 * r, y2, fill=cor, outline="")
        self.create_oval(x2 - 2 * r, y2 - 2 * r, x2, y2, fill=cor, outline="")
        self.create_rectangle(x1, y1 + r, x2, y2 - r, fill=cor, outline="")
        self.create_rectangle(x1 + r, y1, x2 - r, y2, fill=cor, outline="")

    def _desenhar(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w <= 2 or h <= 2:
            w = int(self.cget("width")) or 120
            h = int(self.cget("height")) or 36

        if self._desabilitado:
            fill_c = "#1e222d"
            bord_c = "#252a38"
            txt_c = TEXT_MUTED
        elif self._estado_atual == "click":
            fill_c = self.click_cor
            bord_c = self.hover_border_cor
            txt_c = self.fg_cor
        elif self._estado_atual == "hover":
            fill_c = self.hover_cor
            bord_c = self.hover_border_cor
            txt_c = self.fg_cor
        else:
            fill_c = self.bg_cor
            bord_c = self.border_cor
            txt_c = self.fg_cor

        raio_efetivo = min(self.raio, h // 2)

        self._desenhar_forma_arredondada(0, 0, w, h, raio_efetivo, bord_c)
        self._desenhar_forma_arredondada(1, 1, w - 1, h - 1, max(1, raio_efetivo - 1), fill_c)

        cy = (h // 2) + self._offset_y
        if self.alinhar == "left":
            self.create_text(self.pad_x, cy, text=self.texto, fill=txt_c, font=self.fonte_obj, anchor="w")
        else:
            self.create_text(w // 2, cy, text=self.texto, fill=txt_c, font=self.fonte_obj, anchor="center")

    def _on_enter(self, e):
        if not self._desabilitado:
            self._estado_atual = "hover"
            self._desenhar()

    def _on_leave(self, e):
        if not self._desabilitado:
            self._estado_atual = "normal"
            self._offset_y = 0
            self._desenhar()

    def _on_press(self, e):
        if not self._desabilitado:
            self._estado_atual = "click"
            self._offset_y = 1
            self._desenhar()

    def _on_release(self, e):
        if not self._desabilitado:
            self._estado_atual = "hover"
            self._offset_y = 0
            self._desenhar()
            if self.comando:
                self.comando()

    def configurar_visual(self, texto=None, bg_cor=None, hover_cor=None, click_cor=None, fg_cor=None, border_cor=None):
        if texto is not None:
            self.texto = texto
        if bg_cor is not None:
            self.bg_cor = bg_cor
        if hover_cor is not None:
            self.hover_cor = hover_cor
        if click_cor is not None:
            self.click_cor = click_cor
        if fg_cor is not None:
            self.fg_cor = fg_cor
        if border_cor is not None:
            self.border_cor = border_cor
        self._recalcular_dimensoes()
        self._desenhar()

    def atualizar_fonte(self, familia, tamanho):
        self.fonte_obj.configure(family=familia, size=tamanho)
        self._recalcular_dimensoes()
        self._desenhar()

    def set_disabled(self, desabilitado):
        self._desabilitado = desabilitado
        self.config(cursor="" if desabilitado else "hand2")
        self._desenhar()


# ==========================================
# 13. AÇÕES DA INTERFACE E ESCALA DE FONTE
# ==========================================
def destacar_botao_ativo(botao_selecionado):
    for b in botoes_acao:
        if b is botao_selecionado:
            b.configurar_visual(
                bg_cor=ACCENT_CYAN,
                hover_cor=ACCENT_CYAN_HOVER,
                fg_cor="#0b0e14",
                border_cor=ACCENT_CYAN
            )
            janela.after(850, lambda btn=b: restaurar_botao_acao(btn))
        else:
            restaurar_botao_acao(b)


def restaurar_botao_acao(b):
    if b is btn_guardar_memoria_pill:
        b.configurar_visual(
            bg_cor="#132e26",
            hover_cor="#193d32",
            fg_cor=ACCENT_GREEN,
            border_cor="#059669"
        )
    elif b in (btn_captura, btn_anexar):
        b.configurar_visual(
            bg_cor="#231f38",
            hover_cor="#312b4f",
            fg_cor=ACCENT_VIOLET_HOVER,
            border_cor="#4338ca"
        )
    else:
        b.configurar_visual(
            bg_cor=BG_ELEVATED,
            hover_cor="#2b3347",
            fg_cor=TEXT_PRIMARY,
            border_cor=BORDER_SUBTLE
        )


def acao_capturar_ecra():
    global imagem_anexada_b64
    destacar_botao_ativo(btn_captura)
    janela.withdraw()
    janela.update()
    time.sleep(0.4)
    try:
        imagem_anexada_b64 = capturar_ecra_b64()
        lbl_anexo.config(
            text="📷  Ecrã capturado! Escreve ou fala a tua pergunta abaixo.",
            fg=ACCENT_AMBER
        )
        janela.deiconify()
        caixa_entrada.focus()
        if caixa_entrada.get().strip():
            enviar_mensagem()
    except Exception as e:
        janela.deiconify()
        messagebox.showerror("Erro", f"Não foi possível capturar o ecrã: {e}")


def acao_anexar_imagem():
    global imagem_anexada_b64
    destacar_botao_ativo(btn_anexar)
    caminho = filedialog.askopenfilename(
        title="Escolher Imagem",
        filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp *.bmp")]
    )
    if caminho:
        imagem_anexada_b64 = preparar_imagem_ficheiro_b64(caminho)
        lbl_anexo.config(
            text=f"🖼️  Imagem anexada: {os.path.basename(caminho)} — Escreve ou fala o que queres perguntar.",
            fg=ACCENT_VIOLET_HOVER
        )
        caixa_entrada.focus()


def acao_indexar_ficheiro():
    destacar_botao_ativo(btn_indexar)
    caminho = filedialog.askopenfilename(
        title="Indexar Ficheiro na Base de Dados Vetorial Privada",
        filetypes=[
            ("Documentos e Código", "*.txt *.md *.py *.json *.csv *.log *.cpp *.h *.cs *.ini *.xml"),
            ("Todos os ficheiros", "*.*")
        ]
    )
    if caminho:
        atualizar_estado(f"📚 A indexar {os.path.basename(caminho)} na base vetorial...")
        def _tarefa():
            qtd, erro = indexar_ficheiro_na_base_vetorial(caminho)
            if erro:
                adicionar_ao_chat("Rubos", f"Não foi possível indexar o ficheiro: {erro}", "bot_tag")
            else:
                adicionar_ao_chat(
                    "Rubos",
                    f"Ficheiro '{os.path.basename(caminho)}' indexado com sucesso ({qtd} blocos vetoriais guardados na base privada).",
                    "bot_tag"
                )
            estado_final = "🎙️ Em chamada — a ouvir..." if gestor_voz.ativo else "🟢 Pronto"
            atualizar_estado(estado_final)
        threading.Thread(target=_tarefa, daemon=True).start()


def acao_mostrar_janelas():
    destacar_botao_ativo(btn_janelas)
    janelas = listar_janelas_abertas()
    if not janelas:
        adicionar_ao_chat("Rubos", "Não existem outras janelas visíveis abertas neste momento.", "bot_tag")
        return
    lista = "\n".join([f"• {j['titulo']}  [{j['processo'] or 'Janela'}]" for j in janelas])
    adicionar_ao_chat(
        "Rubos",
        f"Janelas abertas ({len(janelas)}):\n{lista}\n\nPodes dizer ou escrever por exemplo: 'fecha o Chrome' ou 'minimiza o Bloco de Notas'.",
        "bot_tag"
    )


def acao_mostrar_agenda():
    destacar_botao_ativo(btn_agenda)
    adicionar_ao_chat("Rubos", consultar_agenda_texto("todos"), "bot_tag")


def alternar_auto_web():
    global auto_web_ativo
    auto_web_ativo = not auto_web_ativo
    if auto_web_ativo:
        btn_web.configurar_visual(
            texto="🌐  Auto-Web: ON",
            bg_cor="#132e26",
            hover_cor="#193d32",
            click_cor="#214f41",
            fg_cor=ACCENT_GREEN,
            border_cor="#059669"
        )
    else:
        btn_web.configurar_visual(
            texto="🌐  Auto-Web: OFF",
            bg_cor=BG_ELEVATED,
            hover_cor="#2b3347",
            click_cor="#363f57",
            fg_cor=TEXT_SECONDARY,
            border_cor=BORDER_SUBTLE
        )


def alternar_voz_piper():
    global voz_ativa
    voz_ativa = not voz_ativa
    if voz_ativa:
        btn_voz_piper.configurar_visual(
            texto="🔊  Voz PT-PT: ON",
            bg_cor="#132e26",
            hover_cor="#193d32",
            click_cor="#214f41",
            fg_cor=ACCENT_GREEN,
            border_cor="#059669"
        )
    else:
        parar_voz_piper()
        btn_voz_piper.configurar_visual(
            texto="🔇  Voz PT-PT: OFF",
            bg_cor=BG_ELEVATED,
            hover_cor="#2b3347",
            click_cor="#363f57",
            fg_cor=TEXT_SECONDARY,
            border_cor=BORDER_SUBTLE
        )


def atualizar_menus_audio():
    entradas, saidas = listar_dispositivos_audio()

    def _ui():
        sel_in_atual = var_dispositivo_entrada.get()
        menu_entrada["menu"].delete(0, "end")
        for nome in entradas.keys():
            menu_entrada["menu"].add_command(
                label=nome,
                command=lambda n=nome: (var_dispositivo_entrada.set(n), gestor_voz.trocar_microfone_em_curso())
            )
        if sel_in_atual not in entradas:
            var_dispositivo_entrada.set("Padrão do Sistema")

        sel_out_atual = var_dispositivo_saida.get()
        menu_saida["menu"].delete(0, "end")
        for nome in saidas.keys():
            menu_saida["menu"].add_command(
                label=nome,
                command=tk._setit(var_dispositivo_saida, nome)
            )
        if sel_out_atual not in saidas:
            var_dispositivo_saida.set("Padrão do Sistema")

    janela.after(0, _ui)


def limpar_chat():
    global historico_chat, ultimo_prompt_enviado_voz
    parar_voz_piper()
    historico_chat = []
    ultimo_prompt_enviado_voz = ""
    area_chat.config(state=tk.NORMAL)
    area_chat.delete("1.0", tk.END)
    area_chat.config(state=tk.DISABLED)


def guardar_conversa():
    conteudo = area_chat.get("1.0", tk.END).strip()
    if not conteudo:
        return
    caminho = filedialog.asksaveasfilename(
        defaultextension=".txt",
        initialfile=f"conversa_rubos_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
        filetypes=[("Ficheiro de Texto", "*.txt"), ("Markdown", "*.md")]
    )
    if caminho:
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(conteudo)
        messagebox.showinfo("Guardado", "Conversa exportada com sucesso!")


def carregar_modelos_ollama():
    global modelos_instalados
    try:
        res = requests.get("http://localhost:11434/api/tags", timeout=3).json()
        modelos = [m["name"] for m in res.get("models", [])]
        modelos_instalados = modelos
        if modelos:
            def _atualizar_menu():
                menu_modelos["menu"].delete(0, "end")
                for m in modelos:
                    menu_modelos["menu"].add_command(label=m, command=tk._setit(var_modelo, m))

                preferido = next((m for m in modelos if "rubos-livre" in m.lower()), None)
                if not preferido:
                    preferido = next((m for m in modelos if "dolphin" in m.lower()), None)
                if not preferido:
                    preferido = next((m for m in modelos if not modelo_suporta_visao(m)), modelos[0])
                var_modelo.set(preferido)
            janela.after(0, _atualizar_menu)
    except Exception:
        pass


def alterar_zoom_manual(delta):
    global zoom_manual
    zoom_manual = max(0.8, min(1.6, round(zoom_manual + delta, 2)))
    aplicar_escala_tipografica()


def aplicar_escala_tipografica():
    w = max(760, janela.winfo_width())
    h = max(600, janela.winfo_height())

    escala_janela = ((w / 1060.0) * 0.65) + ((h / 820.0) * 0.35)
    escala_total = max(0.85, min(1.75, escala_janela)) * zoom_manual

    sz_chat = max(10, int(round(11.5 * escala_total)))
    sz_input = max(11, int(round(12.5 * escala_total)))
    sz_btn = max(8, int(round(9.2 * escala_total)))
    sz_small = max(8, int(round(8.2 * escala_total)))
    sz_title = max(13, int(round(15 * escala_total)))

    tamanho_fonte_atual["chat"] = sz_chat
    tamanho_fonte_atual["input"] = sz_input
    tamanho_fonte_atual["btn"] = sz_btn
    tamanho_fonte_atual["small"] = sz_small
    tamanho_fonte_atual["title"] = sz_title

    area_chat.config(font=("Segoe UI", sz_chat))
    area_chat.tag_config("user_tag", foreground=ACCENT_CYAN, font=("Segoe UI", sz_btn, "bold"))
    area_chat.tag_config("bot_tag", foreground=ACCENT_GREEN, font=("Segoe UI", sz_btn, "bold"))
    area_chat.tag_config("time_tag", foreground=TEXT_MUTED, font=("Segoe UI", sz_small))
    area_chat.tag_config("body_tag", foreground=TEXT_PRIMARY, font=("Segoe UI", sz_chat), spacing1=3, spacing3=6)
    area_chat.tag_config("spacer_tag", font=("Segoe UI", max(6, sz_small)))

    caixa_entrada.config(font=("Segoe UI", sz_input))

    for om in (menu_modelos, menu_entrada, menu_saida, menu_motor_voz):
        om.config(font=("Segoe UI Semibold", sz_small))
        om["menu"].config(font=("Segoe UI", sz_small))

    lbl_marca.config(font=("Segoe UI", sz_title, "bold"))
    lbl_versao.config(font=("Segoe UI Semibold", sz_small))
    lbl_estado.config(font=("Segoe UI", sz_btn))
    lbl_anexo.config(font=("Segoe UI Semibold", sz_btn))
    lbl_zoom.config(text=f"{int(round(escala_total * 100))}%", font=("Segoe UI", sz_small))

    for sec_lbl in labels_secao_sidebar:
        sec_lbl.config(font=("Segoe UI", sz_small, "bold"))

    for btn in botoes_todos:
        btn.atualizar_fonte("Segoe UI Semibold", sz_btn)

    largura_sidebar = max(235, int(round(250 * escala_total)))
    frame_sidebar.config(width=largura_sidebar)


def _ao_redimensionar_janela(event):
    global _timer_resize
    if event.widget is janela:
        if _timer_resize is not None:
            janela.after_cancel(_timer_resize)
        _timer_resize = janela.after(90, aplicar_escala_tipografica)


def _ao_fechar_janela():
    gestor_voz.parar_silenciosamente()
    janela.destroy()


# ==========================================
# 14. CONSTRUÇÃO DA JANELA PRINCIPAL (LAYOUT MODERNO)
# ==========================================
janela = tk.Tk()
janela.title("Rubos AI — Assistant v5.2")
janela.geometry("1120x860")
janela.minsize(860, 680)
janela.configure(bg=BG_APP)
janela.protocol("WM_DELETE_WINDOW", _ao_fechar_janela)

frame_root = tk.Frame(janela, bg=BG_APP)
frame_root.pack(fill=tk.BOTH, expand=True)

# ------------------------------------------
# BARRA LATERAL ESQUERDA (NAVEGAÇÃO E SISTEMA)
# ------------------------------------------
frame_sidebar = tk.Frame(frame_root, bg=BG_SIDEBAR, width=255)
frame_sidebar.pack(side=tk.LEFT, fill=tk.Y)
frame_sidebar.pack_propagate(False)

separador_vertical = tk.Frame(frame_root, bg=BORDER_SUBTLE, width=1)
separador_vertical.pack(side=tk.LEFT, fill=tk.Y)

frame_brand = tk.Frame(frame_sidebar, bg=BG_SIDEBAR, padx=18, pady=12)
frame_brand.pack(fill=tk.X)

lbl_marca = tk.Label(frame_brand, text="RUBOS", bg=BG_SIDEBAR, fg=TEXT_PRIMARY, font=("Segoe UI", 15, "bold"))
lbl_marca.pack(side=tk.LEFT)

lbl_versao = tk.Label(
    frame_brand, text=" v5.2 ", bg="#1e293b", fg=ACCENT_CYAN,
    font=("Segoe UI Semibold", 8), padx=6, pady=2
)
lbl_versao.pack(side=tk.LEFT, padx=(8, 0))

labels_secao_sidebar = []


def criar_secao_sidebar(titulo):
    lbl = tk.Label(
        frame_sidebar, text=titulo, bg=BG_SIDEBAR, fg=TEXT_MUTED,
        font=("Segoe UI", 8, "bold"), anchor="w", padx=18
    )
    lbl.pack(fill=tk.X, pady=(6, 3))
    labels_secao_sidebar.append(lbl)
    return lbl


def _estilizar_option_menu(om):
    om.config(
        bg=BG_ELEVATED, fg=TEXT_PRIMARY,
        activebackground="#2b3347", activeforeground=TEXT_PRIMARY,
        highlightthickness=1, highlightbackground=BORDER_SUBTLE,
        borderwidth=0, relief=tk.FLAT, font=("Segoe UI Semibold", 8),
        anchor="w", padx=8, pady=4, cursor="hand2"
    )
    om["menu"].config(
        bg=BG_ELEVATED, fg=TEXT_PRIMARY,
        activebackground=ACCENT_CYAN, activeforeground="#0b0e14",
        font=("Segoe UI", 8)
    )


# Secção: Motor IA
criar_secao_sidebar("MOTOR IA")
frame_modelo_box = tk.Frame(frame_sidebar, bg=BG_SIDEBAR, padx=14)
frame_modelo_box.pack(fill=tk.X)

var_modelo = tk.StringVar(value="rubos-livre:latest")
menu_modelos = tk.OptionMenu(frame_modelo_box, var_modelo, "rubos-livre:latest")
_estilizar_option_menu(menu_modelos)
menu_modelos.pack(fill=tk.X)

# Secção: Dispositivos de Áudio & Voz Portuguesa
criar_secao_sidebar("ÁUDIO & VOZ PORTUGUESA")
frame_audio_box = tk.Frame(frame_sidebar, bg=BG_SIDEBAR, padx=14)
frame_audio_box.pack(fill=tk.X)

tk.Label(frame_audio_box, text="🎙️ Microfone (Entrada):", bg=BG_SIDEBAR, fg=TEXT_SECONDARY, font=("Segoe UI", 8), anchor="w").pack(fill=tk.X)
var_dispositivo_entrada = tk.StringVar(value="Padrão do Sistema")
menu_entrada = tk.OptionMenu(frame_audio_box, var_dispositivo_entrada, "Padrão do Sistema")
_estilizar_option_menu(menu_entrada)
menu_entrada.pack(fill=tk.X, pady=(2, 4))

tk.Label(frame_audio_box, text="🔊 Colunas / Auscultadores (Saída):", bg=BG_SIDEBAR, fg=TEXT_SECONDARY, font=("Segoe UI", 8), anchor="w").pack(fill=tk.X)
var_dispositivo_saida = tk.StringVar(value="Padrão do Sistema")
menu_saida = tk.OptionMenu(frame_audio_box, var_dispositivo_saida, "Padrão do Sistema")
_estilizar_option_menu(menu_saida)
menu_saida.pack(fill=tk.X, pady=(2, 4))

tk.Label(frame_audio_box, text="🗣️ Voz Portuguesa (PT-PT):", bg=BG_SIDEBAR, fg=TEXT_SECONDARY, font=("Segoe UI", 8), anchor="w").pack(fill=tk.X)
var_motor_voz = tk.StringVar(value="Automática (PT-PT)")
menu_motor_voz = tk.OptionMenu(
    frame_audio_box,
    var_motor_voz,
    "Automática (PT-PT)",
    "Piper Local (PT-PT)",
    "Neural Online (Duarte PT-PT)",
    "Neural Online (Raquel PT-PT)",
    "Windows Nativa (PT-PT)"
)
_estilizar_option_menu(menu_motor_voz)
menu_motor_voz.pack(fill=tk.X, pady=(2, 5))

btn_atualizar_audio = BotaoArredondado(
    frame_audio_box, "🔄  Atualizar Dispositivos",
    lambda: (destacar_botao_ativo(btn_atualizar_audio), atualizar_menus_audio()),
    raio=10, pad_x=12, pad_y=4, expand_x=True, alinhar="center"
)
btn_atualizar_audio.pack(fill=tk.X)

# Secção: Estado & Permissões
criar_secao_sidebar("ESTADO & PERMISSÕES")
frame_status_btns = tk.Frame(frame_sidebar, bg=BG_SIDEBAR, padx=14)
frame_status_btns.pack(fill=tk.X)

btn_web = BotaoArredondado(
    frame_status_btns, "🌐  Auto-Web: ON", alternar_auto_web,
    bg_cor="#132e26", hover_cor="#193d32", click_cor="#214f41",
    fg_cor=ACCENT_GREEN, border_cor="#059669",
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_web.pack(fill=tk.X, pady=(0, 4))

is_admin_agora = eh_administrador()
btn_admin = BotaoArredondado(
    frame_status_btns,
    "🛡️  Admin: ATIVO" if is_admin_agora else "🛡️  Admin: OFF",
    reiniciar_como_administrador,
    bg_cor="#132e26" if is_admin_agora else "#292218",
    hover_cor="#193d32" if is_admin_agora else "#382f21",
    click_cor="#214f41" if is_admin_agora else "#473b29",
    fg_cor=ACCENT_GREEN if is_admin_agora else ACCENT_AMBER,
    border_cor="#059669" if is_admin_agora else "#b45309",
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_admin.pack(fill=tk.X)

# Secção: Ferramentas do PC & Agenda
criar_secao_sidebar("SISTEMA & AGENDA")
frame_tools_btns = tk.Frame(frame_sidebar, bg=BG_SIDEBAR, padx=14)
frame_tools_btns.pack(fill=tk.X)

btn_agenda = BotaoArredondado(
    frame_tools_btns, "📅  Minha Agenda", acao_mostrar_agenda,
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_agenda.pack(fill=tk.X, pady=(0, 4))

btn_janelas = BotaoArredondado(
    frame_tools_btns, "🪟  Janelas Abertas", acao_mostrar_janelas,
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_janelas.pack(fill=tk.X, pady=(0, 4))

btn_indexar = BotaoArredondado(
    frame_tools_btns, "📚  Indexar Ficheiro", acao_indexar_ficheiro,
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_indexar.pack(fill=tk.X, pady=(0, 4))

btn_pasta = BotaoArredondado(
    frame_tools_btns, "📁  Pasta Imagens", lambda: (destacar_botao_ativo(btn_pasta), abrir_ficheiro_no_windows(PASTA_IMAGENS)),
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_pasta.pack(fill=tk.X)

# Espaçador flexível
tk.Frame(frame_sidebar, bg=BG_SIDEBAR).pack(fill=tk.BOTH, expand=True)

# Secção: Voz & Conversa (Base da Barra Lateral)
frame_chat_btns = tk.Frame(frame_sidebar, bg=BG_SIDEBAR, padx=14, pady=6)
frame_chat_btns.pack(fill=tk.X, side=tk.BOTTOM)

btn_voz_piper = BotaoArredondado(
    frame_chat_btns, "🔊  Voz PT-PT: ON", alternar_voz_piper,
    bg_cor="#132e26", hover_cor="#193d32", click_cor="#214f41",
    fg_cor=ACCENT_GREEN, border_cor="#059669",
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_voz_piper.pack(fill=tk.X, pady=(0, 4))

btn_chamada_side = BotaoArredondado(
    frame_chat_btns, "🎙️  Chamada Voz: OFF", gestor_voz.alternar,
    bg_cor="#132e26", hover_cor="#193d32", click_cor="#214f41",
    fg_cor=ACCENT_GREEN, border_cor="#059669",
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_chamada_side.pack(fill=tk.X, pady=(0, 4))

btn_guardar = BotaoArredondado(
    frame_chat_btns, "💾  Exportar Chat", guardar_conversa,
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_guardar.pack(fill=tk.X, pady=(0, 4))

btn_limpar = BotaoArredondado(
    frame_chat_btns, "🗑️  Limpar Chat", limpar_chat,
    bg_cor="#2b1620", hover_cor="#3b1d2b", click_cor="#4f2539",
    fg_cor=ACCENT_ROSE, border_cor="#be123c",
    raio=12, pad_x=14, pad_y=5, expand_x=True, alinhar="left"
)
btn_limpar.pack(fill=tk.X)


# ------------------------------------------
# ÁREA PRINCIPAL (CHAT + COMPOSER FLUTUANTE)
# ------------------------------------------
frame_main = tk.Frame(frame_root, bg=BG_APP)
frame_main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

frame_header = tk.Frame(frame_main, bg=BG_APP, padx=24, pady=12)
frame_header.pack(fill=tk.X)

lbl_estado = tk.Label(frame_header, text="🟢 Pronto", bg=BG_APP, fg=TEXT_SECONDARY, font=("Segoe UI", 9))
lbl_estado.pack(side=tk.LEFT)

frame_zoom = tk.Frame(frame_header, bg=BG_APP)
frame_zoom.pack(side=tk.RIGHT)

btn_zoom_menos = BotaoArredondado(
    frame_zoom, "A-", lambda: alterar_zoom_manual(-0.1),
    raio=12, pad_x=10, pad_y=4
)
btn_zoom_menos.pack(side=tk.LEFT, padx=(0, 6))

lbl_zoom = tk.Label(frame_zoom, text="100%", bg=BG_APP, fg=TEXT_MUTED, font=("Segoe UI", 8))
lbl_zoom.pack(side=tk.LEFT, padx=4)

btn_zoom_mais = BotaoArredondado(
    frame_zoom, "A+", lambda: alterar_zoom_manual(0.1),
    raio=12, pad_x=10, pad_y=4
)
btn_zoom_mais.pack(side=tk.LEFT, padx=(6, 0))

frame_chat_wrap = tk.Frame(frame_main, bg=BG_APP, padx=24, pady=0)
frame_chat_wrap.pack(fill=tk.BOTH, expand=True)

area_chat = scrolledtext.ScrolledText(
    frame_chat_wrap, wrap=tk.WORD, state=tk.DISABLED,
    font=("Segoe UI", 11), bg=BG_SURFACE, fg=TEXT_PRIMARY,
    insertbackground=TEXT_PRIMARY, relief=tk.FLAT,
    highlightthickness=1, highlightbackground=BORDER_SUBTLE,
    padx=20, pady=18
)
area_chat.pack(fill=tk.BOTH, expand=True)
area_chat.tag_config("user_tag", foreground=ACCENT_CYAN, font=("Segoe UI", 9, "bold"))
area_chat.tag_config("bot_tag", foreground=ACCENT_GREEN, font=("Segoe UI", 9, "bold"))
area_chat.tag_config("time_tag", foreground=TEXT_MUTED, font=("Segoe UI", 8))
area_chat.tag_config("body_tag", foreground=TEXT_PRIMARY, font=("Segoe UI", 11), spacing1=3, spacing3=6)
area_chat.tag_config("spacer_tag", font=("Segoe UI", 8))

lbl_anexo = tk.Label(frame_main, text="", bg=BG_APP, fg=ACCENT_AMBER, font=("Segoe UI Semibold", 9), anchor="w")
lbl_anexo.pack(fill=tk.X, padx=28, pady=(6, 0))

frame_composer_outer = tk.Frame(frame_main, bg=BG_APP, padx=24, pady=16)
frame_composer_outer.pack(fill=tk.X)

frame_composer = tk.Frame(
    frame_composer_outer, bg=BG_SURFACE,
    highlightthickness=1, highlightbackground=BORDER_ACTIVE,
    padx=14, pady=10
)
frame_composer.pack(fill=tk.X)

frame_input_row = tk.Frame(frame_composer, bg=BG_SURFACE)
frame_input_row.pack(fill=tk.X)

caixa_entrada = tk.Entry(
    frame_input_row, font=("Segoe UI", 12),
    bg=BG_SURFACE, fg=TEXT_PRIMARY,
    insertbackground=ACCENT_CYAN, relief=tk.FLAT, bd=0
)
caixa_entrada.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 12), ipady=8)
caixa_entrada.bind("<Return>", lambda event: enviar_mensagem())
caixa_entrada.focus()

btn_enviar = BotaoArredondado(
    frame_input_row, "Enviar  ➤", enviar_mensagem,
    bg_cor=ACCENT_CYAN, hover_cor=ACCENT_CYAN_HOVER, click_cor="#bae6fd",
    fg_cor="#090d16", border_cor=ACCENT_CYAN,
    raio=20, pad_x=22, pad_y=9
)
btn_enviar.pack(side=tk.RIGHT)

tk.Frame(frame_composer, bg=BORDER_SUBTLE, height=1).pack(fill=tk.X, pady=(8, 8))

frame_pills_row = tk.Frame(frame_composer, bg=BG_SURFACE)
frame_pills_row.pack(fill=tk.X)

btn_guardar_memoria_pill = BotaoArredondado(
    frame_pills_row, "🧠 Guardar na Memória",
    lambda: (destacar_botao_ativo(btn_guardar_memoria_pill), enviar_mensagem(forcar_web=True, guardar_memoria=True)),
    bg_cor="#132e26", hover_cor="#193d32", click_cor="#214f41",
    fg_cor=ACCENT_GREEN, border_cor="#059669",
    raio=16, pad_x=14, pad_y=6
)
btn_guardar_memoria_pill.pack(side=tk.LEFT, padx=(0, 8))

btn_captura = BotaoArredondado(
    frame_pills_row, "📷 Capturar Ecrã", acao_capturar_ecra,
    bg_cor="#231f38", hover_cor="#312b4f", click_cor="#3f3763",
    fg_cor=ACCENT_VIOLET_HOVER, border_cor="#4338ca",
    raio=16, pad_x=14, pad_y=6
)
btn_captura.pack(side=tk.LEFT, padx=(0, 8))

btn_anexar = BotaoArredondado(
    frame_pills_row, "🖼️ Anexar Imagem", acao_anexar_imagem,
    bg_cor="#231f38", hover_cor="#312b4f", click_cor="#3f3763",
    fg_cor=ACCENT_VIOLET_HOVER, border_cor="#4338ca",
    raio=16, pad_x=14, pad_y=6
)
btn_anexar.pack(side=tk.LEFT, padx=(0, 8))

btn_pesquisa = BotaoArredondado(
    frame_pills_row, "🔎 Pesquisar Web",
    lambda: (destacar_botao_ativo(btn_pesquisa), enviar_mensagem(forcar_web=True)),
    raio=16, pad_x=14, pad_y=6
)
btn_pesquisa.pack(side=tk.LEFT, padx=(0, 8))

btn_galeria = BotaoArredondado(
    frame_pills_row, "🖼️ Imagens Web",
    lambda: (destacar_botao_ativo(btn_galeria), enviar_mensagem(forcar_imagens=True)),
    raio=16, pad_x=14, pad_y=6
)
btn_galeria.pack(side=tk.LEFT)

botoes_acao = [
    btn_guardar_memoria_pill, btn_captura, btn_anexar, btn_pesquisa, btn_galeria,
    btn_agenda, btn_janelas, btn_indexar, btn_pasta, btn_atualizar_audio
]
botoes_todos = [
    btn_atualizar_audio, btn_web, btn_admin, btn_agenda, btn_janelas, btn_indexar, btn_pasta,
    btn_voz_piper, btn_chamada_side, btn_guardar, btn_limpar,
    btn_zoom_menos, btn_zoom_mais,
    btn_enviar, btn_guardar_memoria_pill, btn_captura, btn_anexar, btn_pesquisa, btn_galeria
]

janela.bind("<Configure>", _ao_redimensionar_janela)
janela.bind("<Control-plus>", lambda e: alterar_zoom_manual(0.1))
janela.bind("<Control-minus>", lambda e: alterar_zoom_manual(-0.1))


# ==========================================
# 15. INICIALIZAÇÃO DO SISTEMA
# ==========================================
def _inicializar_sistema():
    atualizar_menus_audio()
    atualizar_estado("🔄 A iniciar Ollama...")
    garantir_ollama_ativo(timeout_arranque=8.0)
    carregar_modelos_ollama()
    atualizar_estado("⚙️ A indexar aplicações do Windows...")
    indexar_aplicacoes_windows()
    tem_piper = bool(
        PIPER_EXE and os.path.exists(PIPER_EXE)
        and MODELO_PIPER_ONNX and os.path.exists(MODELO_PIPER_ONNX)
        and os.path.getsize(MODELO_PIPER_ONNX) > 1024
    )
    info_voz = "Voz Piper PT-PT" if tem_piper else ("Voz Neural PT-PT" if TEM_EDGE_TTS else "Voz Windows PT-PT")
    atualizar_estado(f"🟢 Pronto ({len(apps_indexadas)} apps | {info_voz})")


threading.Thread(target=_inicializar_sistema, daemon=True).start()
threading.Thread(target=_ciclo_monitor_agenda, daemon=True).start()

adicionar_ao_chat(
    "Rubos",
    "Rubos v5.2 ativo!\n"
    "• Chamada de Voz Contínua: clica em '🎙️ Chamada Voz: OFF' na barra lateral — falas comigo, eu espero 2 segundos, respondo em Português de Portugal e continuo a ouvir-te para conversarmos naturalmente.\n"
    "• Agenda & Dia a dia: podes dizer 'coloca um evento amanhã aula às 9:30', 'o que tenho na agenda hoje?', 'mete um temporizador de 10 minutos', 'aumenta o volume' ou 'quanto é 45 * 12?'.\n"
    "• Conversa normal: podes falar ou escrever naturalmente sobre qualquer tema.",
    "bot_tag"
)

janela.mainloop()