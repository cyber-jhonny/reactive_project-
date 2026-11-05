from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

base = Path.cwd()
interface = base / "interface.py"
package = base / "monitoramento"
sensor_file = package / "sensores.py"

if not interface.exists():
    raise SystemExit("ERRO: interface.py não encontrado.")

source = interface.read_text(encoding="utf-8")

if "from monitoramento.sensores import coletar_dados" in source:
    raise SystemExit("A integração dos sensores já parece instalada. Nada foi alterado.")

required = [
    "        self.build_interface()\n",
    '        status = QLabel("SENSORES AINDA NÃO CONECTADOS")\n',
    '                value_label = QLabel("--")\n',
    "                card_layout.addWidget(value_label)\n",
    "    def show_page(self, index):\n",
]

for anchor in required:
    if source.count(anchor) != 1:
        raise SystemExit(
            "ERRO: não encontrei um ponto de alteração único:\n" + repr(anchor)
            + "\nNenhum arquivo foi alterado."
        )

package.mkdir(exist_ok=True)
(package / "__init__.py").touch(exist_ok=True)

sensor_code = r'''import os
import time
import psutil

_last_time = None
_last_net = None

def coletar_dados():
    global _last_time, _last_net

    agora = time.monotonic()
    cpu = psutil.cpu_percent(interval=None)
    memoria = psutil.virtual_memory()
    disco = psutil.disk_usage(os.environ.get("SystemDrive", "C:") + "\\")

    rede = psutil.net_io_counters()
    download = 0.0
    upload = 0.0

    if _last_time is not None and _last_net is not None:
        intervalo = max(agora - _last_time, 0.001)
        download = max(0, rede.bytes_recv - _last_net.bytes_recv) / intervalo
        upload = max(0, rede.bytes_sent - _last_net.bytes_sent) / intervalo

    _last_time = agora
    _last_net = rede

    return {
        "cpu_percent": cpu,
        "ram_percent": memoria.percent,
        "ram_used_gb": memoria.used / (1024 ** 3),
        "ram_available_gb": memoria.available / (1024 ** 3),
        "disk_percent": disco.percent,
        "disk_used_gb": disco.used / (1024 ** 3),
        "disk_free_gb": disco.free / (1024 ** 3),
        "net_down_mbps": download * 8 / 1_000_000,
        "net_up_mbps": upload * 8 / 1_000_000,
    }
'''
sensor_file.write_text(sensor_code, encoding="utf-8")

backup = base / (
    "interface.backup_sensores_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
)
shutil.copy2(interface, backup)

try:
    source = source.replace(
        "        self.build_interface()\n",
        "        self.build_interface()\n"
        "        from monitoramento.sensores import coletar_dados\n"
        "        self.coletar_dados_monitoramento = coletar_dados\n"
        "        self.monitor_timer = QTimer(self)\n"
        "        self.monitor_timer.timeout.connect(self.update_monitoring_data)\n"
        "        self.monitor_timer.start(2000)\n"
        "        self.update_monitoring_data()\n",
        1
    )

    source = source.replace(
        '        status = QLabel("SENSORES AINDA NÃO CONECTADOS")\n',
        '        status = QLabel("SENSORES INICIALIZANDO")\n'
        "        self.monitor_status = status\n",
        1
    )

    source = source.replace(
        '                value_label = QLabel("--")\n',
        '                value_label = QLabel("--")\n'
        "                if not hasattr(self, 'monitor_values'):\n"
        "                    self.monitor_values = {}\n"
        "                self.monitor_values[key] = value_label\n",
        1
    )

    methods = '''
    def update_monitoring_data(self):
        try:
            dados = self.coletar_dados_monitoramento()

            self.monitor_values["CPU"].setText(
                f'{dados["cpu_percent"]:.1f}%'
            )
            self.monitor_values["RAM"].setText(
                f'{dados["ram_percent"]:.1f}%'
            )
            self.monitor_values["SSD"].setText(
                f'{dados["disk_percent"]:.1f}%'
            )
            self.monitor_values["REDE"].setText(
                f'Down {dados["net_down_mbps"]:.2f} / Up {dados["net_up_mbps"]:.2f} Mbps'
            )
            self.monitor_values["GPU"].setText("N/D")
            self.monitor_values["BENCHMARK"].setText("Não executado")

            self.monitor_status.setText("MONITORAMENTO ATIVO")
        except Exception as exc:
            if hasattr(self, "monitor_status"):
                self.monitor_status.setText("ERRO NA COLETA DE SENSORES")
            print(f"[JARVIS MONITORAMENTO] {exc}")

'''
    source = source.replace(
        "    def show_page(self, index):\n",
        methods + "    def show_page(self, index):\n",
        1
    )

    interface.write_text(source, encoding="utf-8")

    py_compile.compile(str(sensor_file), doraise=True)
    py_compile.compile(str(interface), doraise=True)

    print("SUCESSO: sensores básicos integrados.")
    print("Backup:", backup.name)
    print("Validação de sintaxe: OK")

except Exception as exc:
    shutil.copy2(backup, interface)
    print("ERRO:", exc)
    print("A interface foi restaurada pelo backup.")
    sys.exit(1)
