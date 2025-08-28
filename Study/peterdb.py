from playwright.sync_api import sync_playwright
import time, json, requests, os, traceback
import pymysql


def get_pending_urls(db_config, limit=20):
    """DB에서 target_urls 테이블의 pending URL 불러오기"""
    conn = pymysql.connect(**db_config, charset="utf8mb4", use_unicode=True)
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT id, property_url FROM target_urls WHERE status='pending' ORDER BY created_at ASC LIMIT %s", (limit,))
    results = cursor.fetchall()
    conn.close()
    return results


def update_url_status(db_config, url_id, status):
    """URL 상태 업데이트"""
    conn = pymysql.connect(**db_config, charset="utf8mb4", use_unicode=True)
    cursor = conn.cursor()
    cursor.execute("UPDATE target_urls SET status=%s WHERE id=%s", (status, url_id))
    conn.commit()
    conn.close()


def scrape_peterpan_room_info(url: str, base_dir: str):
    """
    매물 상세 정보 + 이미지 스크래핑 → JSON 반환
    """
    room_info = {}
    property_id = None

    with sync_playwright() as p:
        browser = None
        try:
            browser = p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()

            print(f"\n➡️ {url} 접속 중...")
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            time.sleep(5)

            # 매물 번호
            try:
                id_element = page.locator('#sidebar-content .house-index > span')
                if id_element.is_visible():
                    property_id = id_element.inner_text().strip()
            except Exception:
                pass

            # 테이블 정보
            rows = page.locator('div.detail-table-row').all()
            for row in rows:
                try:
                    key = row.locator('div.detail-table-th').inner_text().strip()
                    value = row.locator('div.detail-table-td').inner_text().strip()
                    if key and value:
                        room_info[key] = value
                except:
                    continue

            # 옵션
            options = [el.inner_text().strip()
                       for el in page.locator('div.detail-option-table dd').all()
                       if el.is_visible()]
            room_info['추가옵션'] = ''
            first = True
            if options:
                for o in options:
                    if first:
                        room_info['추가옵션'] += o
                        first = False
                    else:
                        room_info['추가옵션'] += ', ' + o
                    

            # 주소
            try:
                addr = page.locator('span.address').first.inner_text().strip()
                room_info['주소'] = addr
            except:
                pass

            # 위도, 경도
            try:
                room_info['위도'] = page.locator('meta[property="og:latitude"]').get_attribute('content')
                room_info['경도'] = page.locator('meta[property="og:longitude"]').get_attribute('content')
            except:
                pass

            # 이미지 다운로드
            img_elements = page.locator('#photoCarousel div.carousel-inner img.photo').all()
            photo_urls = [img.get_attribute('src') for img in img_elements if img.get_attribute('src')]

            if property_id:
                img_folder = os.path.join(base_dir, "img")
                os.makedirs(img_folder, exist_ok=True)

                for i, img_url in enumerate(photo_urls, 1):
                    try:
                        r = requests.get(img_url, timeout=10)
                        if r.status_code == 200:
                            filename = os.path.join(img_folder, f"{property_id}_{i}.jpg")
                            with open(filename, 'wb') as f:
                                f.write(r.content)
                    except:
                        continue

        except Exception as e:
            print(f"❌ 오류: {e}")
            print(traceback.format_exc())
        finally:
            if browser:
                browser.close()

    room_info['property_url'] = url
    return room_info, property_id


def main():
    # DB 연결 설정
    db_config = {
        'host': 'localhost',
        'port': 3310,
        'user': 'root',
        'password': '1234',
        'database': 'bangu'
    }

    base_dir = "scraped_data"
    info_dir = os.path.join(base_dir, "info")
    os.makedirs(info_dir, exist_ok=True)

    # DB에서 URL 불러오기
    urls = get_pending_urls(db_config, limit=50)
    if not urls:
        print("⚠️ 처리할 URL이 없습니다.")
        return

    for url_data in urls:
        url_id = url_data['id']
        url = url_data['property_url']

        update_url_status(db_config, url_id, "processing")
        data, pid = scrape_peterpan_room_info(url, base_dir)

        if not pid:
            update_url_status(db_config, url_id, "failed")
            continue

        # JSON 저장
        file_path = os.path.join(info_dir, f"{pid}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        update_url_status(db_config, url_id, "completed")
        print(f"✅ JSON 저장 완료: {file_path}")
        time.sleep(20)


if __name__ == "__main__":
    main()