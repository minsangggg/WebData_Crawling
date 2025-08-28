# Pre_option.py
def parse_options(item):
    """
    피터팬 JSON에서 추가옵션/시설 정보를 추출
    """
    options = item.get("additional_options", {})
    return {
        "is_new_building": options.get("is_new_building", 0),
        "have_parking_lot": options.get("have_parking_lot", 0),
        "is_full_option": options.get("is_full_option", 0),
        "have_elevator": options.get("have_elevator", 0),
        "support_loan": options.get("support_loan", 0),
        "allow_pet": options.get("allow_pet", 0),
        "is_main_road": options.get("is_main_road", 0),
    }
