from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql

app = FastAPI()

class User(BaseModel):
    username: str
    password: str
    nickname: str
    birth: str
    gender: str

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
def login(user: User):
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
    finally:
        conn.close()
