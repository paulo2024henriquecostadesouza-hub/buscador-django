"""
Baixa os relatórios do Selimp (Flip) via Selenium e importa direto no banco.

Uso:
    python manage.py atualizar_flip
    python manage.py atualizar_flip --data-inicio 01/01/2025
    python manage.py atualizar_flip --sem-limpar   (acumula sem apagar dados anteriores)
"""
import os
import time
import winsound
from datetime import date

from django.core.management.base import BaseCommand

from mapa.models import Servico, ImportacaoRelatorio
from mapa.importador import importar_relatorio_flip

# ------------------------------------------------------------------
# Configurações — ajuste aqui se necessário
# ------------------------------------------------------------------
LOGIN_USER       = "CPLU367502"
SENHA_USER       = "85630415"
DATA_INICIO_PAD  = "01/04/2025"
PASTA_DOWNLOADS  = r"C:\Users\CCO-02\Downloads"

ABAS = [
    ("CNC",      "CNC"),
    ("OUVIDORIA","OUVIDORIA"),
    ("BFS",      "BFS"),
    ("ACIC",     "ACIC"),
    ("SAC 156",  "SAC"),
]
# ------------------------------------------------------------------


def _limpar_csvs(pasta):
    """Remove todos os CSVs antigos da pasta de downloads."""
    for f in os.listdir(pasta):
        if f.lower().endswith(".csv"):
            try:
                os.remove(os.path.join(pasta, f))
            except Exception:
                pass


def _aguardar_csv(pasta, timeout=90):
    """Aguarda até que um CSV apareça na pasta; retorna o caminho ou None."""
    for _ in range(timeout):
        arquivos = [
            os.path.join(pasta, f)
            for f in os.listdir(pasta)
            if f.lower().endswith(".csv")
        ]
        if arquivos:
            return max(arquivos, key=os.path.getmtime)
        time.sleep(1)
    return None


def _importar_csv(caminho_csv, fonte, stdout, style):
    """Abre o CSV e chama o importador Django passando a fonte explicitamente."""
    time.sleep(5)  # garante que o Windows liberou o arquivo

    nome = os.path.basename(caminho_csv)

    for tentativa in range(1, 6):
        try:
            with open(caminho_csv, "rb") as f:
                class _Wrapper:
                    name = nome
                    def read(self_):
                        return f.read()

                total = importar_relatorio_flip(_Wrapper(), fonte)

            try:
                os.remove(caminho_csv)
            except Exception:
                pass

            stdout.write(style.SUCCESS(f"  ✓ {nome} [{fonte}]: {total} registros importados"))
            return total

        except PermissionError:
            stdout.write(f"  [BLOQUEIO] Arquivo em uso. Tentativa {tentativa}/5...")
            winsound.Beep(800, 600)
            time.sleep(10)

        except Exception as e:
            stdout.write(f"  [ERRO] Tentativa {tentativa}/5: {e}")
            time.sleep(5)

    stdout.write(style.ERROR(f"  ✗ Não foi possível importar {nome} após 5 tentativas."))
    return 0


class Command(BaseCommand):
    help = "Baixa relatórios do Selimp via Selenium e importa direto no banco Django"

    def add_arguments(self, parser):
        parser.add_argument(
            "--data-inicio",
            default=DATA_INICIO_PAD,
            help=f"Data de início para o filtro (padrão: {DATA_INICIO_PAD})",
        )
        parser.add_argument(
            "--sem-limpar",
            action="store_true",
            default=False,
            help="Acumula dados sem apagar os existentes",
        )

    def handle(self, *args, **options):
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from webdriver_manager.chrome import ChromeDriverManager

        data_inicio = options["data_inicio"]
        sem_limpar  = options["sem_limpar"]
        hoje        = date.today().strftime("%d/%m/%Y")

        self.stdout.write(f"\n{'='*55}")
        self.stdout.write(f"  ATUALIZAR FLIP — {hoje}")
        self.stdout.write(f"  Período: {data_inicio} → {hoje}")
        self.stdout.write(f"  Abas: {', '.join(a for a, _ in ABAS)}")
        self.stdout.write(f"{'='*55}\n")

        # Limpa dados anteriores (opcional)
        if not sem_limpar:
            total_apagados = Servico.objects.count()
            Servico.objects.all().delete()
            ImportacaoRelatorio.objects.filter(tipo="relatorio").delete()
            self.stdout.write(f"  {total_apagados} registros apagados.\n")

        # Configura o Chrome — força download sem popup e sem confirmação
        prefs = {
            "download.default_directory":   PASTA_DOWNLOADS,
            "download.prompt_for_download": False,
            "download.directory_upgrade":   True,
            "safebrowsing.enabled":         False,
            "safebrowsing.disable_download_protection": True,
        }
        options_chrome = webdriver.ChromeOptions()
        options_chrome.add_experimental_option("prefs", prefs)
        options_chrome.add_argument("--window-size=1920,1080")
        options_chrome.add_argument("--safebrowsing-disable-download-protection")
        options_chrome.add_argument("--safebrowsing-disable-extension-blacklist")

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options_chrome,
        )
        wait = WebDriverWait(driver, 30)
        total_geral = 0

        try:
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Acessando Selimp...")
            driver.get("https://selimp25.sflip.online/")
            wait.until(EC.presence_of_element_located((By.ID, "Login"))).send_keys(LOGIN_USER)
            driver.find_element(By.ID, "Senha").send_keys(SENHA_USER)
            driver.find_element(By.ID, "btnEntrar").click()
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Login OK.\n")

            # ── 1. CNC ──────────────────────────────────────────────
            _limpar_csvs(PASTA_DOWNLOADS)
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Baixando CNC...")
            wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[data-target='#menu-CNC']")
            )).click()
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[@id='menu-CNC']//a[contains(text(), 'Consulta')]")
            )).click()
            wait.until(EC.element_to_be_clickable((By.ID, "inpDataInicial"))).send_keys(
                Keys.CONTROL + "a", Keys.BACKSPACE
            )
            driver.find_element(By.ID, "inpDataInicial").send_keys(data_inicio)
            driver.find_element(By.ID, "inpDataFinal").send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.ID, "inpDataFinal").send_keys(hoje)
            driver.find_element(By.ID, "btn_Filtrar").send_keys(Keys.TAB, Keys.ENTER)
            csv_path = _aguardar_csv(PASTA_DOWNLOADS)
            if csv_path:
                total_geral += _importar_csv(csv_path, 'CNC', self.stdout, self.style)
            else:
                self.stderr.write("  [ERRO] CSV do CNC não encontrado.")

            # ── 2. OUVIDORIA ─────────────────────────────────────────
            _limpar_csvs(PASTA_DOWNLOADS)
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Baixando OUVIDORIA...")
            wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[data-target='#menu-SAC156-Ouvidoria']")
            )).click()
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="menu-SAC156-Ouvidoria"]/ul/li[2]/a')
            )).click()
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="inpDataInicial_Consulta"]')
            )).send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.XPATH, '//*[@id="inpDataInicial_Consulta"]').send_keys(data_inicio)
            driver.find_element(By.ID, "inpDataFinal").send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.ID, "inpDataFinal").send_keys(hoje)
            driver.find_element(By.ID, "btn_Filtrar").send_keys(Keys.TAB, Keys.ENTER)
            csv_path = _aguardar_csv(PASTA_DOWNLOADS)
            if csv_path:
                total_geral += _importar_csv(csv_path, 'OUVIDORIA', self.stdout, self.style)
            else:
                self.stderr.write("  [ERRO] CSV da OUVIDORIA não encontrado.")

            # ── 3. BFS ───────────────────────────────────────────────
            _limpar_csvs(PASTA_DOWNLOADS)
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Baixando BFS...")
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="menu_bfs"]/a')
            )).click()
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="menu_bfs_consulta"]/a')
            )).click()
            wait.until(EC.element_to_be_clickable((By.ID, "inpDataInicial"))).send_keys(
                Keys.CONTROL + "a", Keys.BACKSPACE
            )
            driver.find_element(By.ID, "inpDataInicial").send_keys(data_inicio)
            driver.find_element(By.ID, "inpDataFinal").send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.ID, "inpDataFinal").send_keys(hoje)
            driver.find_element(By.ID, "btn_Filtrar").send_keys(Keys.TAB, Keys.ENTER)
            csv_path = _aguardar_csv(PASTA_DOWNLOADS)
            if csv_path:
                total_geral += _importar_csv(csv_path, 'BFS', self.stdout, self.style)
            else:
                self.stderr.write("  [ERRO] CSV do BFS não encontrado.")

            # ── 4. ACIC ──────────────────────────────────────────────
            _limpar_csvs(PASTA_DOWNLOADS)
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Baixando ACIC...")
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="menu_acic"]/a')
            )).click()
            time.sleep(2)
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//*[@id="menu_acic"]//a[contains(text(), "Consulta")]')
            )).click()
            wait.until(EC.element_to_be_clickable((By.ID, "inpDataInicial"))).send_keys(
                Keys.CONTROL + "a", Keys.BACKSPACE
            )
            driver.find_element(By.ID, "inpDataInicial").send_keys(data_inicio)
            driver.find_element(By.ID, "inpDataFinal").send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.ID, "inpDataFinal").send_keys(hoje)
            driver.find_element(By.ID, "btn_Filtrar").send_keys(Keys.TAB, Keys.ENTER)
            csv_path = _aguardar_csv(PASTA_DOWNLOADS)
            if csv_path:
                total_geral += _importar_csv(csv_path, 'ACIC', self.stdout, self.style)
            else:
                self.stderr.write("  [ERRO] CSV do ACIC não encontrado.")

            # ── 5. SAC 156 ───────────────────────────────────────────
            _limpar_csvs(PASTA_DOWNLOADS)
            self.stdout.write(f"[{time.strftime('%H:%M:%S')}] Baixando SAC 156...")
            wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "a[data-target='#menu-SAC156']")
            )).click()
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//*[@id='menu-SAC156']//a[contains(text(), 'Consulta')]")
            )).click()
            wait.until(EC.element_to_be_clickable(
                (By.ID, "inpDataInicial_Consulta")
            )).send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.ID, "inpDataInicial_Consulta").send_keys(data_inicio)
            driver.find_element(By.ID, "inpDataFinal").send_keys(Keys.CONTROL + "a", Keys.BACKSPACE)
            driver.find_element(By.ID, "inpDataFinal").send_keys(hoje)
            driver.find_element(By.ID, "logradouro").click()
            for _ in range(2):
                driver.switch_to.active_element.send_keys(Keys.TAB)
            driver.switch_to.active_element.send_keys(Keys.ENTER)
            csv_path = _aguardar_csv(PASTA_DOWNLOADS)
            if csv_path:
                total_geral += _importar_csv(csv_path, 'SAC', self.stdout, self.style)
            else:
                self.stderr.write("  [ERRO] CSV do SAC 156 não encontrado.")

            winsound.Beep(1000, 400)
            winsound.Beep(1200, 300)
            self.stdout.write(self.style.SUCCESS(
                f"\n[{time.strftime('%H:%M:%S')}] CONCLUÍDO — {total_geral} serviços importados."
            ))

        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"\n[ERRO GERAL]: {exc}"))
            winsound.Beep(440, 1000)
        finally:
            driver.quit()
