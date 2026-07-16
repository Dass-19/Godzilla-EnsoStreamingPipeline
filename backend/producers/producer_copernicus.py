"""
Script de Ingesta para Copernicus Marine Service.
Obtiene TODAS las variables oceanográficas clave para la predicción de El Niño:
1. ZOS (Sea Surface Height) -> Ondas Kelvin
2. MLOTST (Mixed Layer Thickness) -> Dinámica de la termoclina
3. THETAO (Sea Surface Temperature) -> Anomalías de temperatura (SST)
4. SO (Sea Surface Salinity) -> Estratificación salina
5. UO, VO (Currents) -> Corrientes zonales y meridionales
"""


from common.kafka_client import build_producer, send_record, run_loop

import datetime
import traceback

# Datasets divididos por variable en la nueva arquitectura de Copernicus
DATASETS = {
    "2D": "cmems_mod_glo_phy_anfc_0.083deg_P1D-m",       # zos, mlotst
    "SST": "cmems_mod_glo_phy-thetao_anfc_0.083deg_P1D-m", # thetao
    "SAL": "cmems_mod_glo_phy-so_anfc_0.083deg_P1D-m",     # so
    "CUR": "cmems_mod_glo_phy-cur_anfc_0.083deg_P1D-m"     # uo, vo
}

def test_connection():
    print("[*] Iniciando sesión en Copernicus Marine Service con credenciales...")
    try:
        # pyrefly: ignore [missing-import]
        import copernicusmarine
        copernicusmarine.login(username="mbarco", password="GentedeVerg@01")
        print("[+] Login exitoso en Copernicus Marine")
        return True
    except ImportError:
        print("[-] El paquete 'copernicusmarine' no está instalado. Instálalo con 'pip install copernicusmarine'")
        return False
    except Exception as e:
        print(f"[-] Fallo en el login de Copernicus: {e}")
        return False

def ingest_data():
    print("[*] Extrayendo variables predictivas para El Niño de Copernicus Marine...")
    try:
        # pyrefly: ignore [missing-import]
        import copernicusmarine
        
        # Filtramos para Niño 3.4 (Aprox Lat -5 a 5, Lon -170 a -120)
        lat_slice = slice(-5, 5)
        lon_slice = slice(-170, -120)
        
        records_by_date = {}

        # 1. Variables 2D (Altura del mar y Capa de Mezcla)
        print(f"[*] Obteniendo ZOS y MLOTST de {DATASETS['2D']}")
        ds_2d = copernicusmarine.open_dataset(dataset_id=DATASETS["2D"])
        subset_2d = ds_2d[['zos', 'mlotst']].sel(latitude=lat_slice, longitude=lon_slice)
        recent_times = subset_2d.time[-5:].values
        
        for t in recent_times:
            dt = datetime.datetime.fromtimestamp(t.astype('O') / 1e9, datetime.UTC)
            date_str = dt.strftime('%Y-%m-%d')
            
            daily_slice = subset_2d.sel(time=t)
            records_by_date[date_str] = {
                "date": date_str,
                "zos_meters": float(daily_slice['zos'].mean().values),
                "mlotst_meters": float(daily_slice['mlotst'].mean().values)
            }
            
        # 2. Temperatura (SST / Thetao) a profundidad 0
        print(f"[*] Obteniendo THETAO (Temperatura) de {DATASETS['SST']}")
        ds_sst = copernicusmarine.open_dataset(dataset_id=DATASETS["SST"])
        subset_sst = ds_sst['thetao'].sel(latitude=lat_slice, longitude=lon_slice).isel(depth=0)
        for t in recent_times:
            dt = datetime.datetime.fromtimestamp(t.astype('O') / 1e9, datetime.UTC)
            date_str = dt.strftime('%Y-%m-%d')
            if date_str in records_by_date:
                records_by_date[date_str]["thetao_degC"] = float(subset_sst.sel(time=t).mean().values)
                
        # 3. Salinidad (SO) a profundidad 0
        print(f"[*] Obteniendo SO (Salinidad) de {DATASETS['SAL']}")
        ds_sal = copernicusmarine.open_dataset(dataset_id=DATASETS["SAL"])
        subset_sal = ds_sal['so'].sel(latitude=lat_slice, longitude=lon_slice).isel(depth=0)
        for t in recent_times:
            dt = datetime.datetime.fromtimestamp(t.astype('O') / 1e9, datetime.UTC)
            date_str = dt.strftime('%Y-%m-%d')
            if date_str in records_by_date:
                records_by_date[date_str]["so_psu"] = float(subset_sal.sel(time=t).mean().values)

        # 4. Corrientes (UO, VO) a profundidad 0
        print(f"[*] Obteniendo UO, VO (Corrientes) de {DATASETS['CUR']}")
        ds_cur = copernicusmarine.open_dataset(dataset_id=DATASETS["CUR"])
        subset_cur = ds_cur[['uo', 'vo']].sel(latitude=lat_slice, longitude=lon_slice).isel(depth=0)
        for t in recent_times:
            dt = datetime.datetime.fromtimestamp(t.astype('O') / 1e9, datetime.UTC)
            date_str = dt.strftime('%Y-%m-%d')
            if date_str in records_by_date:
                daily_slice = subset_cur.sel(time=t)
                records_by_date[date_str]["uo_velocity_m_s"] = float(daily_slice['uo'].mean().values)
                records_by_date[date_str]["vo_velocity_m_s"] = float(daily_slice['vo'].mean().values)

        return {
            "metadata": {
                "source": "Copernicus Marine Service - GLOBAL_ANALYSISFORECAST_PHY_001_024",
                "region": "Niño 3.4 (Lat -5 a 5, Lon -170 a -120)",
                "variables": [
                    "zos (Sea Surface Height)",
                    "mlotst (Mixed Layer Thickness)",
                    "thetao (Sea Surface Temperature)",
                    "so (Sea Surface Salinity)",
                    "uo (Zonal Current Velocity)",
                    "vo (Meridional Current Velocity)"
                ],
                "timestamp": datetime.datetime.now(datetime.UTC).isoformat()
            },
            "data": list(records_by_date.values())
        }
            
    except Exception as e:
        print(f"[-] Error al descargar/procesar datos de Copernicus: {e}")
        traceback.print_exc()
        return None


def run_producer():
    producer = build_producer()
    def _fetch():
        data = ingest_data()
        if data:
            return [data]
        return []
    run_loop(producer, "copernicus-data", _fetch, interval_seconds=3600)

if __name__ == "__main__":
    run_producer()
