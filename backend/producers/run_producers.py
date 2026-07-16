import subprocess
import time
import sys

producers = [
    "producer_celec_embalse.py",
    "producer_noaa.py",
    "producer_inocar_mareas.py",
    "producer_sngr_alertas.py",
    "producer_gee.py",
    "producer_open_meteo.py",
    "producer_nasa_power.py",
    "producer_openweathermap.py",
    "producer_enso_indexes.py",
    "producer_inamhi.py",
    "producer_sgr_eventos.py",
    "producer_seguraep.py",
    "producer_guayas_osm.py",
    "producer_ndbc_buoys.py"
]

print("Iniciando todos los productores...")

processes = []
for p in producers:
    print(f"Levantando {p}...")
    # Use unbuffered output to ensure logs appear immediately in docker
    process = subprocess.Popen([sys.executable, "-u", p])
    processes.append(process)
    time.sleep(1)

print("Todos los productores han sido lanzados en segundo plano.")

try:
    for process in processes:
        process.wait()
except KeyboardInterrupt:
    print("Deteniendo productores...")
    for process in processes:
        process.terminate()
