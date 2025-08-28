import mariadb
import sys

try:
    conn_src = mariadb.connect(
        user="lguplus7",
        password="lg7p@ssw0rd~!",
        host="192.168.14.40",
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

src_cur.execute("select * from room")
res = src_cur.fetchall()
print(f'fetched {len(res)} records')
tar_cur.execute('delete from room')
conn_tar.commit()
for record in res:
    tar_cur.execute("insert into room values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" , (record))
    conn_tar.commit()
    
    
src_cur.execute("select * from images")
res2 = src_cur.fetchall()
print(f'fetched {len(res2)} records')
tar_cur.execute('delete from images')
conn_tar.commit()
for record in res2:
    tar_cur.execute("insert into images values (?,?,?,?,?,?)" , (record))
    conn_tar.commit()
        
src_cur.close()
conn_src.close()
tar_cur.close()
conn_tar.close()