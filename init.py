"""
Descargador automático de archivos ZIP desde el portal SEPS.
Requiere un archivo .env con SEPS_USUARIO y SEPS_CLAVE definidos.

Las pausas entre acciones están calibradas para simular comportamiento
humano y evitar bloqueos de IP — no reducir estos tiempos.
"""

import os
import time
import logging
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, WebDriverException

# ─────────────────────────────────────────────
# Logs
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Pausa humana — NO modificar estos tiempos
# ─────────────────────────────────────────────
def esperar(segundos=2):
    """Pausa que simula tiempo de reacción humano entre acciones."""
    time.sleep(segundos)


# ─────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────
@dataclass
class Config:
    usuario: str
    clave: str
    download_dir: Path
    login_url: str = (
        "https://servicios.seps.gob.ec/sca/seguridades/paginas/accesos/seleccionOrganizacion.jsf"
    )
    timeout: int = 20
    download_timeout: int = 90
    # ↓ Cambia solo aquí cuando cambie la fecha o carpeta
    ruta_carpetas: tuple = field(
        default_factory=lambda: ("Providencias_Judiciales", "2026", "MARZO", "16-04-2026")
    )


def cargar_config() -> Config:
    """Carga credenciales desde el archivo .env."""
    load_dotenv()
    usuario = os.getenv("SEPS_USUARIO")
    clave = os.getenv("SEPS_CLAVE")

    if not usuario or not clave:
        raise EnvironmentError(
            "Faltan credenciales. Define SEPS_USUARIO y SEPS_CLAVE en tu archivo .env"
        )

    download_dir = Path.home() / "Downloads"
    download_dir.mkdir(parents=True, exist_ok=True)
    return Config(usuario=usuario, clave=clave, download_dir=download_dir)


# ─────────────────────────────────────────────
# Navegador
# ─────────────────────────────────────────────
def crear_driver(download_dir: Path) -> webdriver.Firefox:
    """Inicializa Firefox con preferencias de descarga silenciosa."""
    options = Options()
    options.set_preference("browser.download.folderList", 2)
    options.set_preference("browser.download.dir", str(download_dir))
    options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip")
    options.set_preference("pdfjs.disabled", True)
    options.set_preference("browser.download.manager.showWhenStarting", False)
    options.set_preference("browser.download.useDownloadDir", True)
    options.set_preference("dom.webnotifications.enabled", False)
    return webdriver.Firefox(options=options)


# ─────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────
def scroll_into_view(driver: webdriver.Firefox, element) -> None:
    """Desplaza el elemento al centro de la vista y espera como un humano."""
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(1)  # pausa original — no reducir


def scroll_hasta_cargar_todos(driver: webdriver.Firefox, max_intentos: int = 5) -> None:
    """Hace scroll en el contenedor hasta que no aparezcan más archivos."""
    contenedor = driver.find_element(By.CLASS_NAME, "elfinder-cwd-wrapper")
    cantidad_anterior = -1
    intentos_sin_cambio = 0

    while intentos_sin_cambio < max_intentos:
        cantidad_actual = len(
            driver.find_elements(By.XPATH, "//div[contains(@class, 'elfinder-cwd-file')]")
        )
        if cantidad_actual == cantidad_anterior:
            intentos_sin_cambio += 1
        else:
            intentos_sin_cambio = 0
            cantidad_anterior = cantidad_actual

        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", contenedor)
        time.sleep(1.5)  # pausa original — no reducir

    log.info(f"Scroll completado — elementos detectados: {cantidad_anterior}")


def clic_en_nodo(driver: webdriver.Firefox, wait: WebDriverWait, texto: str) -> None:
    """Busca un nodo del árbol por texto, hace scroll y clic con pausa humana."""
    elemento = wait.until(
        EC.presence_of_element_located((By.XPATH, f"//span[text()='{texto}']"))
    )
    scroll_into_view(driver, elemento)
    driver.execute_script("arguments[0].click();", elemento)
    esperar()  # 2 segundos — pausa original entre clics de navegación
    log.info(f"Carpeta abierta: {texto}")


# ─────────────────────────────────────────────
# Flujo principal
# ─────────────────────────────────────────────
def iniciar_sesion(driver: webdriver.Firefox, wait: WebDriverWait, config: Config) -> None:
    driver.get(config.login_url)
    esperar()  # 2s — esperar carga de página

    wait.until(EC.presence_of_element_located((By.NAME, "j_idt21:j_idt28"))).send_keys(config.usuario)
    esperar()  # 2s — pausa entre campos como un humano
    driver.find_element(By.NAME, "j_idt21:j_idt30").send_keys(config.clave)
    esperar()  # 2s — pausa antes de hacer clic en login
    driver.find_element(By.ID, "j_idt21:j_idt33").click()
    time.sleep(10)  # esperar carga completa tras login — no reducir
    log.info("Sesión iniciada.")


def navegar_a_carpeta(driver: webdriver.Firefox, wait: WebDriverWait, config: Config) -> None:
    wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Casillero SEPS"))).click()
    esperar()  # 2s — esperar apertura del casillero

    for carpeta in config.ruta_carpetas:
        clic_en_nodo(driver, wait, carpeta)


def descargar_archivo(
    driver: webdriver.Firefox,
    actions: ActionChains,
    div,
    download_dir: Path,
    timeout: int,
) -> bool:
    """Descarga un archivo con doble clic respetando pausas humanas."""
    nombre = div.get_attribute("title").strip()
    ruta_destino = download_dir / nombre

    try:
        scroll_into_view(driver, div)
        esperar(0.5)  # pequeña pausa antes del doble clic — pausa original

        actions.move_to_element(div).double_click().perform()
        esperar(1)  # pausa tras doble clic — pausa original

        for _ in range(timeout):
            archivo_parcial = Path(str(ruta_destino) + ".part")
            if ruta_destino.exists() and not archivo_parcial.exists():
                log.info(f"✅ Descargado: {nombre}")
                return True
            time.sleep(1)

        log.warning(f"⏰ Timeout al descargar: {nombre}")
        return False

    except WebDriverException as e:
        log.error(f"Error de navegador al descargar '{nombre}': {e}")
        return False


def descargar_todos_los_zips(
    driver: webdriver.Firefox,
    wait: WebDriverWait,
    actions: ActionChains,
    config: Config,
) -> None:
    wait.until(EC.presence_of_element_located((By.CLASS_NAME, "elfinder-cwd")))
    esperar()  # 2s — esperar render del contenedor
    scroll_hasta_cargar_todos(driver)

    zip_divs = driver.find_elements(
        By.XPATH,
        "//div[contains(@class, 'elfinder-cwd-filename') and contains(@title, '.zip')]",
    )
    log.info(f"Archivos .zip encontrados: {len(zip_divs)}")

    exitosos, fallidos = 0, 0

    for div in zip_divs:
        nombre = div.get_attribute("title").strip()
        log.info(f"⬇  Descargando: {nombre}")
        if descargar_archivo(driver, actions, div, config.download_dir, config.download_timeout):
            exitosos += 1
        else:
            fallidos += 1
        esperar(1)  # 1s entre descargas — pausa original

    log.info(f"Resumen — ✅ Exitosos: {exitosos} | ❌ Fallidos: {fallidos}")


# ─────────────────────────────────────────────
# Entrada
# ─────────────────────────────────────────────
if __name__ == "__main__":
    config = cargar_config()
    driver = crear_driver(config.download_dir)
    wait = WebDriverWait(driver, config.timeout)
    actions = ActionChains(driver)

    try:
        iniciar_sesion(driver, wait, config)
        navegar_a_carpeta(driver, wait, config)
        descargar_todos_los_zips(driver, wait, actions, config)
        log.info("🎉 Proceso completado.")
    except TimeoutException as e:
        log.error(f"Timeout esperando un elemento: {e}")
    except EnvironmentError as e:
        log.error(str(e))
    except Exception as e:
        log.exception(f"Error inesperado: {e}")
    finally:
        driver.quit()
        log.info("Navegador cerrado.")