from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql
from fastapi.staticfiles import StaticFiles
import os


app = FastAPI()
# 프로젝트 안 images 디렉토리를 정적 경로로 마운트

class User(BaseModel):
    username: str
    password: str
    nickname: str
    birth: str
    gender: str

# 로그인 전용 (새로 추가)
class LoginUser(BaseModel):
    username: str
    password: str
    
# CORS 허용 (HTML에서 API 호출 가능하게 해줌)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포 시 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 연결 설정
db_config = {
    "host": "localhost",
    "port": 3310,   # 민상님 환경 맞춤 포트
    "user": "root",
    "password": "1234",
    "database": "bangu"
}

# -----------------------
# 매물 목록 API
# -----------------------
@app.get("/rooms")
def get_rooms():
    conn = pymysql.connect(**db_config, charset="utf8mb4")
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT r.id, r.property_address, r.transaction_type, r.management_fee,
               r.deposit, r.rent,
               (SELECT image_path FROM images WHERE property_id = r.id ORDER BY image_order ASC LIMIT 1) as thumbnail
        FROM room r
        LIMIT 20
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows


@app.post("/login")
def login(user: LoginUser):
    conn = pymysql.connect(**db_config, charset="utf8mb4")
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM users WHERE username=%s AND password=%s", 
                   (user.username, user.password))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {"message": "로그인 성공!", "nickname": result["nickname"]}
    else:
        return {"error": "아이디 또는 비밀번호가 틀렸습니다."}


# -----------------------
# 회원가입 API
# -----------------------


@app.post("/signup")
def signup(user: User):
    conn = pymysql.connect(**db_config, charset="utf8mb4")
    cursor = conn.cursor()
    try:
        sql = """
        INSERT INTO users (username, password, nickname, birth, gender)
        VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(sql, (
            user.username,
            user.password,
            user.nickname,
            user.birth,
            user.gender
        ))
        conn.commit()
        return {"message": "회원가입 성공!"}
    except Exception as e:
        conn.rollback()
        return {"error": str(e)}
    
@app.get("/room/{room_id}")
def get_room(room_id: int):
    conn = pymysql.connect(**db_config, charset="utf8mb4")
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT id, property_address, transaction_type, deposit, rent, management_fee,
               latitude, longitude
        FROM room WHERE id=%s
    """, (room_id,))
    room = cursor.fetchone()

    cursor.execute("SELECT image_path FROM images WHERE property_id=%s ORDER BY image_order", (room_id,))
    rows = cursor.fetchall()

    # 파일명만 추출 → URL 변환
    images = []
    for r in rows:
        filename = r["image_path"]
        images.append({"image_path": f"http://127.0.0.1:8000/images/{filename}"})

    conn.close()
    return {"room": room, "images": images}

app.mount("/images", StaticFiles(directory="C:/githome/WebData_Crawling/Study/scraped_data/img"), name="images")