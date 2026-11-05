import os
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
