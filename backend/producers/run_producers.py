"""
Supervisor de los productores Kafka dentro del contenedor `producers`.

Mantiene vivos los productores de larga duración: si alguno muere, lo reinicia
con un backoff creciente y lo registra.

Los jobs one-shot (capas geográficas que se descargan enteras) se ejecutan una
vez al arrancar y luego cada `INTERVALO_ONESHOT` segundos, sin reinicio en
bucle.

Ctrl+C / SIGTERM detiene todo de forma coordinada.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

DIRECTORIO = Path(__file__).resolve().parent

# Productores de larga duración: corren su propio `run_loop` y no deben salir.
PRODUCTORES_CONTINUOS = [
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
    "producer_ndbc_buoys.py",
]

# Jobs que descargan un snapshot completo y terminan.
PRODUCTORES_ONESHOT = [
    "producer_guayas_osm.py",
    "producer_seguraep.py",
]

# producer_copernicus.py no está en ninguna lista: requiere credenciales
# (COPERNICUS_USERNAME/PASSWORD) y el paquete `copernicusmarine`, que no está
# en requirements.txt. Se ejecuta a mano cuando ambas cosas estén disponibles.

INTERVALO_ONESHOT = int(os.environ.get("INTERVALO_ONESHOT", 6 * 60 * 60))
BACKOFF_INICIAL_S = 5
BACKOFF_MAXIMO_S = 300

_detener = False


def _pedir_parada(signum, _frame):
    global _detener
    print(f"[!] Señal {signum} recibida, deteniendo productores...", flush=True)
    _detener = True


def _lanzar(script: str) -> subprocess.Popen:
    print(f"[*] Levantando {script}...", flush=True)
    # -u: salida sin buffer, para que los logs aparezcan en `docker logs`.
    return subprocess.Popen([sys.executable, "-u", str(DIRECTORIO / script)], cwd=DIRECTORIO)


def main() -> None:
    signal.signal(signal.SIGINT, _pedir_parada)
    signal.signal(signal.SIGTERM, _pedir_parada)

    supervisados = {}
    for script in PRODUCTORES_CONTINUOS:
        supervisados[script] = {
            "proceso": _lanzar(script),
            "backoff": BACKOFF_INICIAL_S,
            "reintento_en": 0.0,
            "reinicios": 0,
        }
        time.sleep(1)

    oneshot = {script: 0.0 for script in PRODUCTORES_ONESHOT}

    print(
        f"[+] {len(supervisados)} productores supervisados, "
        f"{len(oneshot)} jobs one-shot cada {INTERVALO_ONESHOT}s.",
        flush=True,
    )

    try:
        while not _detener:
            ahora = time.monotonic()

            for script, estado in supervisados.items():
                proceso = estado["proceso"]
                if proceso is not None and proceso.poll() is None:
                    continue

                if proceso is not None:
                    estado["reinicios"] += 1
                    print(
                        f"[-] {script} terminó con código {proceso.returncode} "
                        f"(reinicio #{estado['reinicios']}); "
                        f"reintento en {estado['backoff']}s",
                        flush=True,
                    )
                    estado["proceso"] = None
                    estado["reintento_en"] = ahora + estado["backoff"]
                    estado["backoff"] = min(estado["backoff"] * 2, BACKOFF_MAXIMO_S)
                    continue

                if ahora >= estado["reintento_en"]:
                    estado["proceso"] = _lanzar(script)

            for script, proximo in list(oneshot.items()):
                if ahora >= proximo:
                    proceso = _lanzar(script)
                    proceso.wait()
                    print(
                        f"[+] {script} finalizó con código {proceso.returncode}",
                        flush=True,
                    )
                    oneshot[script] = time.monotonic() + INTERVALO_ONESHOT

            time.sleep(2)
    finally:
        for script, estado in supervisados.items():
            proceso = estado["proceso"]
            if proceso is not None and proceso.poll() is None:
                print(f"[*] Deteniendo {script}...", flush=True)
                proceso.terminate()

        for estado in supervisados.values():
            proceso = estado["proceso"]
            if proceso is None:
                continue
            try:
                proceso.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proceso.kill()


if __name__ == "__main__":
    main()
