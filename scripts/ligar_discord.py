import sys
import time

try:
    import pyautogui
except ImportError:
    print("Falta instalar o pyautogui. Executa: pip install pyautogui")
    sys.exit(1)

pyautogui.FAILSAFE = True

# Coordenadas opcionais do botão de chamada de voz no topo do Discord (X, Y).
# Se quiseres clicar automaticamente no botão de chamada, mede a posição com pyautogui.position()
# e preenche aqui, por exemplo: COORD_CHAMADA = (1280, 72)
COORD_CHAMADA = None


def main():
    if len(sys.argv) < 2:
        print("Indica o nome do contacto ou canal.")
        sys.exit(1)

    contacto = " ".join(sys.argv[1:]).strip()
    time.sleep(0.8)

    # Abre o Quick Switcher do Discord (Ctrl+K) e seleciona o contacto/canal
    pyautogui.hotkey("ctrl", "k")
    time.sleep(0.4)
    pyautogui.write(contacto, interval=0.03)
    time.sleep(0.6)
    pyautogui.press("enter")
    time.sleep(0.8)

    if COORD_CHAMADA:
        pyautogui.click(COORD_CHAMADA[0], COORD_CHAMADA[1])
        print(f"Abri a conversa com '{contacto}' no Discord e cliquei no botão de chamada.")
    else:
        print(f"Abri a conversa com '{contacto}' no Discord. (Configura COORD_CHAMADA em ligar_discord.py para clicar no botão de chamada.)")


if __name__ == "__main__":
    main()