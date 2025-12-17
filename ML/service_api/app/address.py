# app/address.py
def merge_address(road_address: str | None, jibun_address: str | None, building_name: str | None) -> str:
    parts = []
    if road_address and road_address.strip():
        parts.append(road_address.strip())
    if jibun_address and jibun_address.strip():
        parts.append(jibun_address.strip())
    if building_name and building_name.strip():
        parts.append(building_name.strip())
    return " ".join(parts)
