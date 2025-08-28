# Insert_info.py
import pymysql
import json

def insert_room_info(room_data, options, image_list):
    """
    room_info + room_images 테이블에 데이터 적재
    """
    conn = pymysql.connect(
        host="localhost",
        user="lguplus7",
        password="lg7p@ssw0rd~!",
        db="cp_data",
        port=3310,
        charset="utf8mb4"
    )
    cursor = conn.cursor()

    # room_info 테이블 insert
    sql_info = """
    INSERT INTO room_info
    (hidx, subject, room_type, room_count, supplied_size, real_size, floor, total_floor,
     floor_text, contract_type, building_type, deposit, monthly_fee, maintenance_cost,
     created_at, live_start_date, address, latitude, longitude, options)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    cursor.execute(sql_info, (
        room_data.get("hidx"), room_data.get("subject"), room_data.get("room_type"),
        room_data.get("room_count"), room_data.get("supplied_size"), room_data.get("real_size"),
        room_data.get("floor"), room_data.get("total_floor"), room_data.get("floor_text"),
        room_data.get("contract_type"), room_data.get("building_type"), room_data.get("deposit"),
        room_data.get("monthly_fee"), room_data.get("maintenance_cost"),
        room_data.get("created_at"), room_data.get("live_start_date"),
        room_data.get("address"), room_data.get("latitude"), room_data.get("longitude"),
        json.dumps(options, ensure_ascii=False)
    ))
    room_id = cursor.lastrowid

    # room_images 테이블 insert
    if image_list:
        sql_img = "INSERT INTO room_images (room_id, image_url) VALUES (%s, %s)"
        for i, img in enumerate(image_list, start=1):
            img_name = f"{i}.jpg"   # 1.jpg, 2.jpg 형식
            cursor.execute(sql_img, (room_id, img_name))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"✅ DB 저장 완료: {room_data.get('subject')}")
