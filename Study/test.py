import mariadb
import sys

try:
    conn_src = mariadb.connect(
        user="lguplus7",
        password="lg7p@ssw0rd~!",
        host="192.168.14.98",
        port=3310,
        database="bangu"
    )
    conn_tar = mariadb.connect(
        user="lguplus7",
        password="lg7p@ssw0rd~!",
        host="localhost",
        port=3310,
        database="bangu"
    )
except mariadb.Error as e:
    print(f"Error connecting to MariaDB Platform: {e}")
    sys.exit(1)

src_cur = conn_src.cursor()
tar_cur = conn_tar.cursor()

# -------------------
# ROOM 테이블
# -------------------
src_cur.execute("SELECT * FROM room")
res = src_cur.fetchall()
print(f'fetched {len(res)} records from source.room')

for record in res:
    # room 테이블이 27개의 컬럼이라고 가정
    tar_cur.execute("""
        INSERT IGNORE INTO room VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, record)
conn_tar.commit()

# -------------------
# IMAGES 테이블
# -------------------
src_cur.execute("SELECT * FROM images")
res2 = src_cur.fetchall()
print(f'fetched {len(res2)} records from source.images')

for record in res2:
    tar_cur.execute("""
        INSERT IGNORE INTO images VALUES (?, ?, ?, ?, ?, ?)
    """, record)
conn_tar.commit()

# 연결 종료
src_cur.close()
conn_src.close()
tar_cur.close()
conn_tar.close()
