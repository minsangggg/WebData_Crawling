import os, json, pymysql, re

# JSON → DB 컬럼 매핑
COLUMN_MAPPING = {
    "위도": "latitude",
    "경도": "longitude",
    "거래방식": "transaction_type",
    "관리비": "management_fee",
    "융자금": "loan_amount",
    "입주가능일": "move_in_date",
    "전입신고 여부": "residence_report",
    "건축물용도": "building_usage",
    "건물형태": "building_type",
    "전용/계약면적": "exclusive_area",
    "전용/공급면적": "exclusive_area",
    "해당층/전체층": "floor_info",
    "방/욕실개수": "room_bathroom_count",
    "방거실형태": "room_living_type",
    "주실기준/방향": "main_room_direction",
    "주차": "parking_info",
    "위반건축물 여부": "illegal_building",
    "사용승인일": "completion_date",
    "사용검사일": "completion_date",
    "준공인가일": "completion_date",
    "냉방시설": "cooling_system",
    "생활시설": "living_facilities",
    "보안시설": "security_facilities",
    "추가옵션": "additional_options",
    "주소": "property_address"
}

def process_rent_data(data_list):
    """
    임대료 데이터 리스트에서 보증금, 월세, 거래방식을 추출하는 함수.
    
    Args:
        data_list (list): 임대료 정보가 포함된 문자열 리스트.
    
    Returns:
        list: 보증금, 월세, 거래방식이 분리된 튜플 리스트.
              (deposit, monthly_rent, transaction_type_str)
              - deposit: 보증금 (int)
              - monthly_rent: 월세 (int) 또는 0
              - transaction_type_str: 거래방식 문자열 (str)
    """
    processed_data = []
    
    for item in data_list:
        # 데이터에서 모든 공백을 제거
        clean_item = item.replace(" ", "")
        transaction_type_str = ""
        deposit = None
        rent = None

        # 가장 구체적인 조건부터 확인: '단기임대'가 포함된 경우
        if '단기임대' in clean_item:
            transaction_type_str = "단기임대"
            
            # '단기임대'이면서 보증금/월세 형식인 경우
            if '/' in clean_item:
                parts = clean_item.split('/')
                deposit_str = parts[0].replace('단기임대', '')
                rent_str = parts[1]
                
                if '억' in deposit_str:
                    deposit_parts = deposit_str.split('억')
                    deposit = int(re.sub(r'[^0-9]', '', deposit_parts[0])) * 100000000
                    if len(deposit_parts) > 1 and deposit_parts[1]:
                        deposit += int(re.sub(r'[^0-9]', '', deposit_parts[1])) * 10000
                else:
                    deposit = int(re.sub(r'[^0-9]', '', deposit_str)) * 10000
                
                rent = int(re.sub(r'[^0-9]', '', rent_str)) * 10000
            
            # '단기임대'이면서 전세(보증금만) 형식인 경우
            else:
                amount_str = re.sub(r'단기임대', '', clean_item)
                if '억' in amount_str:
                    parts = amount_str.split('억')
                    deposit = int(re.sub(r'[^0-9]', '', parts[0])) * 100000000
                    if len(parts) > 1 and parts[1]:
                        deposit += int(re.sub(r'[^0-9]', '', parts[1])) * 10000
                else:
                    deposit = int(re.sub(r'[^0-9]', '', amount_str)) * 10000
                rent = 0 # 단기임대인데 월세가 없는 경우
            
            processed_data.append((deposit, rent, transaction_type_str))

        # '전세'가 포함된 경우
        elif '전세' in clean_item:
            amount_str = re.sub(r'전세', '', clean_item)
            transaction_type_str = "전세"
            
            deposit = 0
            if '억' in amount_str:
                parts = amount_str.split('억')
                deposit += int(re.sub(r'[^0-9]', '', parts[0])) * 100000000
                if len(parts) > 1 and parts[1]:
                    deposit += int(re.sub(r'[^0-9]', '', parts[1])) * 10000
            else:
                deposit = int(re.sub(r'[^0-9]', '', amount_str)) * 10000

            rent = 0
            
            processed_data.append((deposit, rent, transaction_type_str))
        
        # 보증금/월세 형식 (전세, 단기임대 제외)
        elif '/' in clean_item:
            parts = clean_item.split('/')
            deposit_str = parts[0]
            rent_str = parts[1]
            transaction_type_str = "월세"
            
            deposit = 0
            if '억' in deposit_str:
                deposit_parts = deposit_str.split('억')
                deposit += int(re.sub(r'[^0-9]', '', deposit_parts[0])) * 100000000
                if len(deposit_parts) > 1 and deposit_parts[1]:
                    deposit += int(re.sub(r'[^0-9]', '', deposit_parts[1])) * 10000
            else:
                deposit = int(re.sub(r'[^0-9]', '', deposit_str)) * 10000
            
            rent = int(re.sub(r'[^0-9]', '', rent_str)) * 10000
            
            processed_data.append((deposit, rent, transaction_type_str))

        else:
            print(f"알 수 없는 형식: {item}")
            processed_data.append((None, None, None))
            
    return processed_data

def parse_management_fee(text):
    """
    주어진 텍스트에서 관리비 정보를 추출하여 계산하는 함수.
    """
    # 전처리: 텍스트를 줄 단위로 분리하고 공백 제거
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # '없음' 케이스 처리
    if not lines or lines[0] == '없음':
        return 0

    # '관리비 확인 불가' 텍스트가 없는 경우, 첫 줄에 금액이 명시된 경우
    if "관리비 확인 불가" not in text:
        amount_match = re.search(r'(\d+)만원', lines[0])
        if amount_match:
            return int(amount_match.group(1)) * 10000
    
    # 관리비 합계가 명시된 경우
    total_fee_match = re.search(r'관리비 합계\n정액 관리비 (\d+)만원', text)
    if total_fee_match:
        base_fee = int(total_fee_match.group(1))
        return base_fee * 10000
    
    # 미등기 건물 등 관리비 확인 불가 케이스
    unknown_fee_match = re.search(r'관리비 확인 불가', text)
    if unknown_fee_match:
        amount_match = re.search(r'(\d+)만원', lines[1])
        if amount_match:
            return int(amount_match.group(1)) * 10000
        
    return None    

def extract_first_m2_value(text_list):
    """
    주어진 문자열 리스트에서 각 문자열의 첫 번째 'm2' 앞의 float 값을 추출합니다.

    Args:
        text_list (list): 'm2' 값을 포함하는 문자열 리스트. 예: ['22.73m2/43.21m2 (6.88평/13.07평)']

    Returns:
        list: 각 문자열에서 추출된 float 값 리스트.
              추출에 실패한 경우 None을 포함합니다.
    """
    results = []
    # 정규 표현식 패턴:
    # \d+ : 하나 이상의 숫자 (0-9)
    # \.? : 점(.)이 0개 또는 1개
    # \d+ : 하나 이상의 숫자
    # m2  : 'm2' 문자열
    pattern = re.compile(r'(\d+\.?\d+)m2')

    for text in text_list:
        match = pattern.search(text)
        if match:
            # 첫 번째 그룹에 해당하는 값 (숫자)을 float으로 변환하여 추가
            results.append(float(match.group(1)))
        else:
            results.append(None) # 패턴을 찾지 못한 경우 None 추가
    return results

def insert_room_and_images(db_config, json_file, image_dir="scraped_data/img"):
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # property_url과 property_id 확인
    property_url = data.get("property_url")
    property_id = os.path.splitext(os.path.basename(json_file))[0]

    # DB 데이터 변환
    db_data = {"property_url": property_url}
    for k, v in data.items():
        if k in COLUMN_MAPPING:
            col = COLUMN_MAPPING[k]
            if col == 'transaction_type':
                # process_rent_data 함수가 이제 세 번째 값을 반환하므로 이를 처리하도록 수정
                temp = process_rent_data([v])
                for deposit, rent, transaction_type_str in temp:
                    db_data['deposit'] = deposit
                    db_data['rent'] = rent
                    db_data['transaction_type'] = transaction_type_str
            elif col == "management_fee":
                db_data[col] = parse_management_fee(v)
            elif col == "exclusive_area":
                db_data[col] = extract_first_m2_value([v])[0]
            else:
                db_data[col] = v

    # DB 연결
    conn = pymysql.connect(**db_config, charset="utf8mb4", use_unicode=True, autocommit=False)
    cursor = conn.cursor()

    try:
        cols = ", ".join(db_data.keys())
        vals = ", ".join(["%s"] * len(db_data))
        sql = f"""
        INSERT INTO room ({cols})
        VALUES ({vals})
        ON DUPLICATE KEY UPDATE {", ".join([f"{c}=VALUES({c})" for c in db_data.keys() if c != "property_url"])}
        """
        cursor.execute(sql, list(db_data.values()))

        # room_id 가져오기
        room_id = cursor.lastrowid
        if not room_id:
            cursor.execute("SELECT id FROM room WHERE property_url=%s", (property_url,))
            row = cursor.fetchone()
            room_id = row[0] if row else None

        # 이미지 테이블 insert
        if room_id:
            cursor.execute("DELETE FROM images WHERE property_id=%s", (room_id,))
            if os.path.exists(image_dir):
                for fname in os.listdir(image_dir):
                    if fname.startswith(property_id):
                        file_path = os.path.join(image_dir, fname)
                        order = int(fname.split("_")[-1].split(".")[0])
                        is_thumb = (order == 1)
                        cursor.execute(
                            "INSERT INTO images (property_id, image_path, image_order, is_thumbnail) VALUES (%s, %s, %s, %s)",
                            (room_id, f"{image_dir}/{fname}", order, is_thumb)
                        )

        conn.commit()
        print(f"✅ {json_file} → DB 적재 완료 (room_id={room_id})")

    except Exception as e:
        conn.rollback()
        print(f"❌ {json_file} → DB 적재 실패: {e}")

    finally:
        conn.close()


def main():
    db_config = {
        'host': 'localhost',
        'port': 3310,
        'user': 'root',
        'password': '1234',
        'database': 'bangu'
    }

    json_dir = "scraped_data/info"
    for fname in os.listdir(json_dir):
        if fname.endswith(".json"):
            insert_room_and_images(db_config, os.path.join(json_dir, fname))


if __name__ == "__main__":
    main()