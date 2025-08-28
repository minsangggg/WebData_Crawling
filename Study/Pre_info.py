# Pre_info.py
def parse_room_info(item):
    """
    피터팬 JSON에서 매물 기본/거래 정보를 추출
    """
    room_data = {
        "hidx": item.get("hidx"),  # 고유 ID
        "subject": item.get("info", {}).get("subject"),
        "room_type": item.get("info", {}).get("room_type"),
        "room_count": item.get("info", {}).get("room_count"),
        "supplied_size": item.get("info", {}).get("supplied_size"),
        "real_size": item.get("info", {}).get("real_size"),
        "floor": item.get("floor", {}).get("target"),
        "total_floor": item.get("floor", {}).get("total"),
        "floor_text": item.get("floor", {}).get("floor_text_detail"),
        "contract_type": item.get("type", {}).get("contract_type"),
        "building_type": item.get("type", {}).get("building_type_text"),
        "deposit": item.get("price", {}).get("deposit"),
        "monthly_fee": item.get("price", {}).get("monthly_fee"),
        "maintenance_cost": item.get("price", {}).get("maintenance_cost"),
        "created_at": item.get("info", {}).get("created_at"),
        "live_start_date": item.get("info", {}).get("live_start_date"),
        "address": item.get("location", {}).get("address", {}).get("text"),
        "latitude": item.get("location", {}).get("coordinate", {}).get("latitude"),
        "longitude": item.get("location", {}).get("coordinate", {}).get("longitude"),
    }
    return room_data
