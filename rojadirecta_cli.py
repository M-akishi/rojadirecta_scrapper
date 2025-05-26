from playwright.sync_api import sync_playwright
import sys
import os
from InquirerPy import inquirer
import threading
import itertools
import time
import subprocess
from bs4 import BeautifulSoup
import requests

BASE_URL = "https://www.rojadirectaenvivo.pl"
BASE_PATH = os.path.dirname(os.path.abspath(__file__))

def limpiar_consola():
    os.system("cls" if os.name == "nt" else "clear")

def mostrar_cargando(mensaje="Cargando"):
    done = threading.Event()

    def animacion():
        for c in itertools.cycle(['.', '..', '...']):
            if done.is_set():
                break
            sys.stdout.write(f'\r{mensaje}{c}   ')
            sys.stdout.flush()
            time.sleep(0.5)
        sys.stdout.write('\r' + ' ' * (len(mensaje) + 5) + '\r')

    t = threading.Thread(target=animacion)
    t.start()

    return done.set

def crear_navegador_headless():
    ## Navegador Sin interfaz Firefox
    p = sync_playwright().start()
    firefox_path = os.path.join(BASE_PATH, ".local-browsers", "firefox-1482", "firefox", "firefox.exe")
    browser = p.firefox.launch(headless=True, executable_path=firefox_path)
    context = browser.new_context(user_agent="Mozilla/5.0")
    page = context.new_page()
    return p, browser, context, page

def obtener_eventos():
    response = requests.get(BASE_URL)
    response.raise_for_status()  # Lanza error si falla la conexión
    html = response.text

    # Parsear HTML con BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # Buscar el <ul class="menu">
    menu = soup.find('ul', class_='menu')
    if not menu:
        print("No se encontró el <ul class='menu'>")
        exit()

    eventos = []

    # Iterar sobre eventos (li directos del ul.menu)
    for evento in menu.find_all('li', recursive=False):
        a_titulo = evento.find('a')
        if not a_titulo:
            continue

        titulo = a_titulo.get_text(strip=True, separator=' ')

        # Buscar los canales (ul anidado)
        canales_ul = evento.find('ul')
        canales = []
        if canales_ul:
            for canal_li in canales_ul.find_all('li'):
                canal_a = canal_li.find('a')
                if canal_a and canal_a.has_attr('href'):
                    canales.append({
                        'nombre': canal_a.get_text(strip=True),
                        'url': canal_a['href']
                    })

        eventos.append({
            'evento': titulo,
            'canales': canales
        })

    return eventos

def capturar_m3u8(canal_url, timeout=15):
    p, browser, context, page = crear_navegador_headless()
    m3u8_url = None
    stop_animation = mostrar_cargando("Cargando Canal")
    try:
        def manejar_respuesta(response):
            nonlocal m3u8_url
            if ".m3u8" in response.url:
                m3u8_url = response.url

        page.on("response", manejar_respuesta)
        page.goto(canal_url)

        # Esperar hasta que se capture la URL o se agote el timeout
        inicio = time.time()
        while m3u8_url is None and (time.time() - inicio) < timeout:
            time.sleep(0.1)

    finally:
        stop_animation()
        browser.close()
        p.stop()

    return m3u8_url

def reproducir_en_mpv(url):
    try:
        subprocess.run(["mpv", url])
    except Exception as e:
        print(f"Error al ejecutar MPV: {e}")

def main():
    while True:
        limpiar_consola()
        eventos = obtener_eventos()
        if not eventos:
            print("No se encontraron eventos.")
            return

        eleccion = inquirer.select(
            message="Elija el evento:",
            choices=[evento['evento'] for evento in eventos] + ["Salir"]
        ).execute()
        
        if eleccion == "Salir":
            limpiar_consola()
            break        

        seleccionado = next((s for s in eventos if s['evento'] == eleccion), None)

        while True:
            canales = seleccionado["canales"]
            limpiar_consola()                        
            eleccion = inquirer.select(
                message="Canales disponibles para " + seleccionado['evento'],
                choices=[canal['nombre'] for canal in canales] + ["Cancelar"]
            ).execute()
            if eleccion == "Cancelar":
                limpiar_consola()
                break

            canal = next((s for s in canales if s['nombre'] == eleccion), None)
            m3u8 = capturar_m3u8(canal["url"])

            if m3u8:
                reproducir_en_mpv(m3u8)
                break
            else:
                print("Canal no disponible o stream caído. Elige otro canal.")

if __name__ == "__main__":
    main()
