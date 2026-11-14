"""
Buscador real de negocios locales sin sitio web usando la API oficial de OpenStreetMap (0.6 map.json).
Prioriza negocios con correo electronico publico y excluye escuelas/consulados/entidades publicas.
Genera:
  - crm-clientes/prospectos_sin_web.json
  - crm-clientes/prospectos_sin_web.csv
  - crm-clientes/prospectos_data.js
"""

import argparse
import csv
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

OSM_MAP_ENDPOINT = "https://api.openstreetmap.org/api/0.6/map.json"

# Zonas comerciales activas: (ciudad, pais, codigo_pais, (west, south, east, north))
ZONES = [
    ("Ciudad de México (Roma Norte / Condesa)", "México", "52", (-99.168, 19.412, -99.156, 19.424)),
    ("Ciudad de México (Polanco)", "México", "52", (-99.200, 19.428, -99.188, 19.436)),
    ("Bogotá (Chapinero / Zona T)", "Colombia", "57", (-74.060, 4.650, -74.048, 4.672)),
    ("Lima (Miraflores)", "Perú", "51", (-77.035, -12.126, -77.023, -12.114)),
    ("Madrid (Chamberí / Salamanca)", "España", "34", (-3.705, 40.425, -3.693, 40.435)),
    ("Buenos Aires (Palermo)", "Argentina", "54", (-58.432, -34.592, -58.420, -34.580)),
    ("Santiago (Providencia)", "Chile", "56", (-70.618, -33.430, -70.606, -33.418)),
]

EXCLUDED_VALUES = {
    "school", "kindergarten", "university", "college", "diplomatic", "embassy",
    "government", "police", "townhall", "courthouse", "post_office", "library",
    "public_building", "fire_station", "place_of_worship", "community_centre",
    "social_facility", "ngo", "association", "educational_institution",
}

FOOD_TAGS = {"restaurant", "cafe", "fast_food", "bakery", "bar", "pub", "ice_cream", "pastry", "confectionery", "food"}
HEALTH_TAGS = {"dentist", "clinic", "doctors", "pharmacy", "veterinary", "beauty", "hairdresser", "optician", "massage"}

CATEGORY_MAP = {
    "restaurant": ("Restaurante", "restaurante"),
    "cafe": ("Cafetería", "restaurante"),
    "fast_food": ("Comida Rápida", "restaurante"),
    "bakery": ("Panadería / Pastelería", "restaurante"),
    "pastry": ("Pastelería / Repostería", "restaurante"),
    "bar": ("Bar / Restobar", "restaurante"),
    "pub": ("Bar / Pub", "restaurante"),
    "ice_cream": ("Heladería", "restaurante"),
    "food": ("Tienda Gourmet / Alimentos", "restaurante"),
    "dentist": ("Dentista / Clínica Dental", "clinica"),
    "clinic": ("Clínica / Consultorio", "clinica"),
    "doctors": ("Consultorio Médico", "clinica"),
    "beauty": ("Salón de Belleza / Estética", "clinica"),
    "hairdresser": ("Peluquería / Barbería", "clinica"),
    "veterinary": ("Veterinaria", "clinica"),
    "optician": ("Óptica", "clinica"),
    "car_repair": ("Taller Mecánico", "servicios"),
    "bicycle": ("Tienda / Taller de Bicicletas", "servicios"),
    "hardware": ("Ferretería", "servicios"),
    "electronics": ("Tienda / Reparación Electrónica", "servicios"),
    "estate_agent": ("Inmobiliaria", "servicios"),
    "clothes": ("Tienda de Ropa", "servicios"),
    "perfumery": ("Perfumería / Boutique", "servicios"),
    "convenience": ("Tienda / Abarrotes", "servicios"),
    "laundry": ("Lavandería / Tintorería", "servicios"),
    "travel_agency": ("Agencia de Viajes", "servicios"),
    "lawyer": ("Despacho Jurídico", "servicios"),
    "accountant": ("Contabilidad / Asesoría", "servicios"),
    "art": ("Galería / Arte", "servicios"),
}

COMMERCIAL_KEYS = ("amenity", "shop", "office", "craft", "healthcare")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def shrink_bbox(bbox: tuple, factor: float = 0.72) -> tuple:
    w, s, e, n = bbox
    cx, cy = (w + e) / 2.0, (s + n) / 2.0
    hw, hh = (e - w) * factor / 2.0, (n - s) * factor / 2.0
    return (round(cx - hw, 6), round(cy - hh, 6), round(cx + hw, 6), round(cy + hh, 6))


def fetch_osm_bbox(bbox: tuple) -> dict:
    current = bbox
    last_err = None
    for attempt in range(3):
        w, s, e, n = current
        url = f"{OSM_MAP_ENDPOINT}?bbox={w},{s},{e},{n}"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "ImpulsoWebLeadFinder/1.1"},
            )
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            last_err = err
            if err.code == 400:
                current = shrink_bbox(current, 0.65)
                time.sleep(0.5)
                continue
            time.sleep(1.0)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as err:
            last_err = err
            time.sleep(1.0)
    raise RuntimeError(f"No se pudo consultar OSM 0.6 API: {last_err}")


def clean_email(raw_email: str) -> str:
    if not raw_email:
        return ""
    first = re.split(r"[;,\s]+", raw_email.strip())[0]
    first = first.replace("mailto:", "").strip()
    return first if EMAIL_RE.match(first) else ""


def normalize_phone(raw_phone: str, country_code: str) -> str:
    if not raw_phone:
        return ""
    first = re.split(r"[;/,]", raw_phone)[0].strip()
    digits = re.sub(r"\D", "", first)
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if country_code and not digits.startswith(country_code):
        trimmed = digits.lstrip("0")
        if len(trimmed) <= 10:
            digits = f"{country_code}{trimmed}"
    return digits


def is_excluded(tags: dict) -> bool:
    for key in COMMERCIAL_KEYS:
        val = (tags.get(key) or "").strip().lower()
        if val in EXCLUDED_VALUES:
            return True
    if tags.get("amenity") == "arts_centre" and "salón" in (tags.get("name") or "").lower():
        return False
    return False


def detect_category(tags: dict) -> tuple:
    for key in COMMERCIAL_KEYS:
        val = tags.get(key)
        if not val:
            continue
        if val in CATEGORY_MAP:
            return CATEGORY_MAP[val]
        if val in FOOD_TAGS:
            return (val.replace("_", " ").title(), "restaurante")
        if val in HEALTH_TAGS or key == "healthcare":
            return (val.replace("_", " ").title(), "clinica")
        return (val.replace("_", " ").title(), "servicios")
    return ("Comercio Local", "servicios")


def format_address(tags: dict) -> str:
    street = tags.get("addr:street", "")
    num = tags.get("addr:housenumber", "")
    suburb = tags.get("addr:suburb") or tags.get("addr:neighbourhood") or ""
    parts = [p for p in [f"{street} {num}".strip(), suburb] if p]
    return ", ".join(parts) if parts else "Ver ubicación en mapa"


def geocode_city(city_name: str) -> list:
    url = (
        "https://nominatim.openstreetmap.org/search?"
        + urllib.parse.urlencode({"q": city_name, "format": "json", "limit": 1})
    )
    req = urllib.request.Request(url, headers={"User-Agent": "ImpulsoWebLeadFinder/1.1"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        res = json.loads(resp.read().decode("utf-8"))
    if not res:
        raise ValueError(f"No se encontró la ciudad: {city_name}")
    lat = float(res[0]["lat"])
    lon = float(res[0]["lon"])
    bbox = (round(lon - 0.004, 6), round(lat - 0.004, 6), round(lon + 0.004, 6), round(lat + 0.004, 6))
    label = res[0].get("display_name", city_name).split(",")[0]
    return [(label, city_name, "", bbox)]


def collect_leads(zones: list, limit_per_zone: int = 20) -> list:
    raw_leads = []
    seen_keys = set()

    for city, country, country_code, bbox in zones:
        print(f"Consultando negocios reales sin web en {city}...", flush=True)
        try:
            payload = fetch_osm_bbox(bbox)
        except Exception as err:
            print(f"  [!] Error en {city}: {err}", flush=True)
            continue

        elements = payload.get("elements", [])
        zone_candidates = []

        for el in elements:
            tags = el.get("tags")
            if not tags:
                continue
            if not any(k in tags for k in COMMERCIAL_KEYS):
                continue
            if is_excluded(tags):
                continue

            name = (tags.get("name") or "").strip()
            if not name:
                continue

            # Excluir si ya tiene sitio web registrado
            if tags.get("website") or tags.get("contact:website") or tags.get("url"):
                continue

            email = clean_email(tags.get("email") or tags.get("contact:email") or "")
            raw_phone = (tags.get("phone") or tags.get("contact:phone") or "").strip()
            digits = normalize_phone(raw_phone, country_code)

            if not email and len(digits) < 7:
                continue

            dedupe_key = f"{name.lower()}::{email.lower() or digits[-7:]}"
            if dedupe_key in seen_keys:
                continue
            seen_keys.add(dedupe_key)

            cat_label, demo_type = detect_category(tags)
            lat = el.get("lat")
            lon = el.get("lon")
            osm_type = el.get("type", "node")
            osm_id = el.get("id")

            zone_candidates.append({
                "nombre": name,
                "categoria": cat_label,
                "demo_recomendada": demo_type,
                "ciudad": city,
                "pais": country,
                "email": email,
                "telefono_raw": raw_phone,
                "telefono_norm": digits,
                "direccion": format_address(tags),
                "lat": lat,
                "lon": lon,
                "osm_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}",
                "fuente": "OpenStreetMap API 0.6",
            })

        # Priorizar dentro de cada zona los que tienen email
        zone_candidates.sort(key=lambda x: (0 if x["email"] else 1, x["nombre"]))
        selected = zone_candidates[:limit_per_zone]
        email_count = sum(1 for x in selected if x["email"])
        raw_leads.extend(selected)
        print(f"  [+] {len(selected)} prospectos ({email_count} con email directo) en {city}.", flush=True)
        time.sleep(0.5)

    # Orden global: primero todos los que tienen email publico
    raw_leads.sort(key=lambda x: (0 if x["email"] else 1, x["ciudad"], x["nombre"]))

    leads = []
    for idx, item in enumerate(raw_leads, start=1):
        leads.append({"id": idx, **item})

    return leads


def save_outputs(leads: list, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, "prospectos_sin_web.json")
    csv_path = os.path.join(out_dir, "prospectos_sin_web.csv")
    js_path = os.path.join(out_dir, "prospectos_data.js")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)

    fieldnames = [
        "id", "nombre", "categoria", "demo_recomendada", "ciudad", "pais",
        "email", "telefono_raw", "telefono_norm", "direccion", "lat", "lon", "osm_url", "fuente"
    ]
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)

    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.PROSPECTOS_DATA = ")
        json.dump(leads, f, ensure_ascii=False, indent=2)
        f.write(";\n")

    with_email = sum(1 for x in leads if x["email"])
    print(f"\nGuardados {len(leads)} prospectos reales ({with_email} con email) en:", flush=True)
    print(f"  - {json_path}", flush=True)
    print(f"  - {csv_path}", flush=True)
    print(f"  - {js_path}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Buscador de negocios locales sin página web.")
    parser.add_argument("--ciudad", type=str, default="", help="Ciudad específica a buscar (opcional)")
    parser.add_argument("--limit", type=int, default=20, help="Máximo por zona")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(script_dir, "crm-clientes")

    zones = geocode_city(args.ciudad) if args.ciudad else ZONES
    leads = collect_leads(zones, limit_per_zone=args.limit)
    save_outputs(leads, out_dir)


if __name__ == "__main__":
    main()
