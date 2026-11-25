import ctypes
import sys

try:
    import pyautogui
    TEM_PAG = True
except ImportError:
    TEM_PAG = False


def alternar_play_pausa():
    if TEM_PAG:
        pyautogui.press("playpause")
        return True
    if sys.platform == "win32":
        # VK_MEDIA_PLAY_PAUSE = 0xB3
        KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0xB3, 0, KEYEVENTF_KEYUP, 0)
        return True
    return False


def main():
    acao = " ".join(sys.argv[1:]).strip().lower() if len(sys.argv) > 1 else "toggle"
    if alternar_play_pausa():
        if acao in ("pausa", "pausar", "parar", "stop"):
            print("Enviei o comando de pausa/reprodução no Spotify.")
        elif acao in ("play", "continuar", "retomar"):
            print("Enviei o comando de play/reprodução no Spotify.")
        else:
            print("Alternei entre play e pausa no Spotify.")
    else:
        print("Não foi possível enviar o comando de multimédia neste sistema.")
        sys.exit(1)


if __name__ == "__main__":
    main()