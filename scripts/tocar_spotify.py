import sys
import time

try:
    import pyautogui
except ImportError:
    print("Falta instalar o pyautogui. Executa: pip install pyautogui")
    sys.exit(1)

pyautogui.FAILSAFE = True


def main():
    if len(sys.argv) < 2:
        print("Indica o nome da música.")
        sys.exit(1)

    musica = " ".join(sys.argv[1:]).strip()
    time.sleep(0.8)

    # Atalho de pesquisa rápida no Spotify desktop (Ctrl+K / Ctrl+L)
    pyautogui.hotkey("ctrl", "l")
    time.sleep(0.3)
    pyautogui.hotkey("ctrl", "a")
    pyautogui.write(musica, interval=0.03)
    time.sleep(0.4)
    pyautogui.press("enter")
    time.sleep(1.2)

    print(f"Pesquisei e enviei '{musica}' para reprodução no Spotify.")


if __name__ == "__main__":
    main()