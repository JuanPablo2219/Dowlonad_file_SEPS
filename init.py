import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# 🔐 Credenciales
USUARIO = "**************"
CLAVE   = "****************"

# 📂 Carpeta de descargas (descargas del sistema)
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 🕒 Pausa personalizada
def esperar(segundos=2):
    time.sleep(segundos)

# 🔽 Scroll dentro del contenedor de archivos
def scroll_en_contenedor_hasta_cargar_todos(driver):
    contenedor = driver.find_element(By.CLASS_NAME, "elfinder-cwd-wrapper")
    num_anterior = -1
    intentos = 0

    while True:
        zip_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'elfinder-cwd-file')]")
        num_actual = len(zip_elements)

        if num_actual == num_anterior:
            intentos += 1
        else:
            intentos = 0
            num_anterior = num_actual

        if intentos >= 5:
            break

        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", contenedor)
        time.sleep(1.5)

# 🔍 Scroll hasta que sea visible (usado antes de hacer clic)
def scroll_into_view(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
    time.sleep(1)

# ⚙️ Opciones de Firefox
options = Options()
options.set_preference("browser.download.folderList", 2)
options.set_preference("browser.download.dir", DOWNLOAD_DIR)
options.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/zip")
options.set_preference("pdfjs.disabled", True)
options.set_preference("browser.download.manager.showWhenStarting", False)
options.set_preference("browser.download.useDownloadDir", True)
options.set_preference("dom.webnotifications.enabled", False)

# 🧭 Iniciar navegador
driver = webdriver.Firefox(options=options)
wait = WebDriverWait(driver, 20)
actions = ActionChains(driver)

# 🔐 Iniciar sesión
driver.get("https://servicios.seps.gob.ec/sca/seguridades/paginas/accesos/seleccionOrganizacion.jsf")
esperar()

wait.until(EC.presence_of_element_located((By.NAME, "j_idt21:j_idt28"))).send_keys(USUARIO)
esperar()
driver.find_element(By.NAME, "j_idt21:j_idt30").send_keys(CLAVE)
esperar()
driver.find_element(By.ID, "j_idt21:j_idt33").click()
time.sleep(10)  # Esperar carga tras login

# 📁 Navegación en árbol
wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Casillero SEPS"))).click()
esperar()

# Expandir "Providencias_Judiciales"
elem_providencias = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='Providencias_Judiciales']")))
scroll_into_view(driver, elem_providencias)
driver.execute_script("arguments[0].click();", elem_providencias)
esperar()

# Clic en "2025"
elem_2025 = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='2025']")))
scroll_into_view(driver, elem_2025)
driver.execute_script("arguments[0].click();", elem_2025)
esperar()

# Clic en "JUNIO"
elem_junio = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='JUNIO']")))
scroll_into_view(driver, elem_junio)
driver.execute_script("arguments[0].click();", elem_junio)
esperar()

# Clic en "02-06-25"
elem_fecha = wait.until(EC.presence_of_element_located((By.XPATH, "//span[text()='23-06-25']")))
scroll_into_view(driver, elem_fecha)
driver.execute_script("arguments[0].click();", elem_fecha)
esperar()

# 🗂️ Esperar archivos y hacer scroll completo
wait.until(EC.presence_of_element_located((By.CLASS_NAME, "elfinder-cwd")))
esperar()
scroll_en_contenedor_hasta_cargar_todos(driver)

# 📦 Obtener todos los archivos ZIP
zip_divs = driver.find_elements(By.XPATH, "//div[contains(@class, 'elfinder-cwd-filename') and contains(@title, '.zip')]")
print(f"✅ Se encontraron {len(zip_divs)} archivos .zip.")

# ⬇ Descargar cada archivo ZIP
for div in zip_divs:
    nombre = div.get_attribute("title").strip()
    ruta_archivo = os.path.join(DOWNLOAD_DIR, nombre)

    try:
        print(f"⬇ Solicitando descarga de: {nombre}")
        
        # Asegurarse de que el elemento esté visible
        scroll_into_view(driver, div)
        esperar(0.5)

        # Doble clic real
        actions.move_to_element(div).double_click().perform()
        esperar(1)

        # ⏳ Esperar que el archivo aparezca (sin .part)
        timeout = 90
        elapsed = 0
        while elapsed < timeout:
            if os.path.exists(ruta_archivo) and not os.path.exists(ruta_archivo + ".part"):
                print(f"✅ Descargado: {nombre}")
                break
            time.sleep(1)
            elapsed += 1
        else:
            print(f"❌ No se descargó completamente tras {timeout} segundos: {nombre}")

    except Exception as e:
        print(f"⚠️ Error al descargar {nombre}: {e}")
    esperar(1)

print("🎉 Todas las descargas se completaron.")
driver.quit()
