import hashlib
import os
import platform
import socket
import subprocess
from datetime import datetime, timedelta

# Limites para manter a execução rápida dentro do timeout do Rubos
MAX_FICHEIROS_VARRIDOS = 50000
MAX_ALERTAS_POR_CATEGORIA = 25
JANELA_RECENTE = datetime.now() - timedelta(days=7)

EXTENSOES_RISCO = {
    ".exe", ".dll", ".bat", ".cmd", ".ps1", ".vbs", ".js", ".hta",
    ".scr", ".pif", ".jar", ".msi", ".iso", ".img", ".lnk", ".reg"
}

PASTAS_ESPERADAS_EXECUTAVEIS = (
    os.path.normcase(r"C:\Windows"),
    os.path.normcase(r"C:\Program Files"),
    os.path.normcase(r"C:\Program Files (x86)"),
    os.path.normcase(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")),
)

PASTAS_IGNORAR = {
    os.path.normcase(r"C:\Windows\WinSxS"),
    os.path.normcase(r"C:\Windows\Installer"),
    os.path.normcase(r"C:\$Recycle.Bin"),
    os.path.normcase(r"C:\System Volume Information"),
}


def run_ps(cmd):
    res = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=15,
    )
    return (res.stdout or res.stderr or "").strip()


def sha256_ficheiro(caminho, max_bytes=10 * 1024 * 1024):
    try:
        if os.path.getsize(caminho) > max_bytes:
            return "(maior que 10 MB - ignorado)"
        h = hashlib.sha256()
        with open(caminho, "rb") as f:
            while True:
                bloco = f.read(65536)
                if not bloco:
                    break
                h.update(bloco)
        return h.hexdigest()[:16] + "..."
    except Exception:
        return "(sem permissao)"


def varrer_sistema_ficheiros(raiz=r"C:\Users"):
    total_vistos = 0
    total_tamanho_mb = 0.0
    exec_fora_padrao = []
    alterados_recentes = []
    maiores_ficheiros = []

    for dirpath, dirnames, filenames in os.walk(raiz, topdown=True):
        dir_norm = os.path.normcase(dirpath)
        if any(dir_norm == ign or dir_norm.startswith(ign + os.sep) for ign in PASTAS_IGNORAR):
            dirnames[:] = []
            continue

        for nome in filenames:
            total_vistos += 1
            if total_vistos > MAX_FICHEIROS_VARRIDOS:
                break

            caminho = os.path.join(dirpath, nome)
            try:
                st = os.stat(caminho)
            except OSError:
                continue

            tamanho = st.st_size
            total_tamanho_mb += tamanho / (1024 * 1024)
            mod_dt = datetime.fromtimestamp(st.st_mtime)
            ext = os.path.splitext(nome)[1].lower()

            caminho_norm = os.path.normcase(caminho)
            esta_em_pasta_padrao = any(
                caminho_norm.startswith(p + os.sep) for p in PASTAS_ESPERADAS_EXECUTAVEIS if p
            )

            if ext in EXTENSOES_RISCO and not esta_em_pasta_padrao:
                if len(exec_fora_padrao) < MAX_ALERTAS_POR_CATEGORIA:
                    exec_fora_padrao.append((caminho, tamanho, mod_dt))

            if mod_dt >= JANELA_RECENTE and ext in EXTENSOES_RISCO:
                if len(alterados_recentes) < MAX_ALERTAS_POR_CATEGORIA:
                    alterados_recentes.append((caminho, tamanho, mod_dt))

            maiores_ficheiros.append((tamanho, caminho))
            if len(maiores_ficheiros) > 200:
                maiores_ficheiros.sort(key=lambda x: x[0], reverse=True)
                maiores_ficheiros = maiores_ficheiros[:10]

        if total_vistos > MAX_FICHEIROS_VARRIDOS:
            break

    maiores_ficheiros.sort(key=lambda x: x[0], reverse=True)
    return {
        "raiz": raiz,
        "total_vistos": total_vistos,
        "atingiu_limite": total_vistos > MAX_FICHEIROS_VARRIDOS,
        "total_tamanho_mb": round(total_tamanho_mb, 1),
        "exec_fora_padrao": exec_fora_padrao,
        "alterados_recentes": alterados_recentes,
        "maiores_ficheiros": maiores_ficheiros[:10],
    }


print("=== RESUMO DE SEGURANCA LOCAL ===")
print(f"Sistema: {platform.system()} {platform.release()} ({platform.version()})")
print(f"Hostname: {socket.gethostname()}")

print("\n--- Windows Defender ---")
print(run_ps("Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled,IoavProtectionEnabled,AntivirusSignatureLastUpdated | Format-List"))

print("\n--- Firewall ---")
print(run_ps("Get-NetFirewallProfile | Select-Object Name,Enabled | Format-Table -AutoSize"))

print("\n--- Portas TCP em escuta (Listening) ---")
print(run_ps("Get-NetTCPConnection -State Listen | Select-Object LocalAddress,LocalPort,OwningProcess | Sort-Object LocalPort | Format-Table -AutoSize"))

print("\n--- Varredura de Ficheiros ---")
alvo_varredura = os.path.expanduser("~")
resultado = varrer_sistema_ficheiros(alvo_varredura)
print(f"Pasta analisada: {resultado['raiz']}")
print(f"Ficheiros inspecionados: {resultado['total_vistos']} (limite: {MAX_FICHEIROS_VARRIDOS})")
if resultado["atingiu_limite"]:
    print("Aviso: limite de ficheiros atingido para evitar tempo excessivo.")
print(f"Volume acumulado: {resultado['total_tamanho_mb']} MB")

print(f"\nExecutaveis/scripts fora de pastas padrao ({len(resultado['exec_fora_padrao'])}):")
for caminho, tam, dt in resultado["exec_fora_padrao"]:
    print(f"  - {caminho} | {tam} B | {dt.strftime('%Y-%m-%d %H:%M')} | SHA256: {sha256_ficheiro(caminho)}")

print(f"\nExecutaveis/scripts modificados nos ultimos 7 dias ({len(resultado['alterados_recentes'])}):")
for caminho, tam, dt in resultado["alterados_recentes"]:
    print(f"  - {caminho} | {tam} B | {dt.strftime('%Y-%m-%d %H:%M')}")

print("\nTop 10 maiores ficheiros:")
for tam, caminho in resultado["maiores_ficheiros"]:
    print(f"  - {caminho} ({round(tam / (1024 * 1024), 2)} MB)")