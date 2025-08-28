from playwright.sync_api import sync_playwright
import time, json, requests, os, traceback

def scrape_peterpan_room_info(url: str, base_dir: str):
    """
    피터팬의 좋은방 구하기 특정 매물의 정보를 구조적으로 스크래핑하고 이미지를 다운로드합니다.
    Args:
        url (str): 스크래핑할 매물 페이지의 URL
        base_dir (str): 스크래핑된 데이터를 저장할 기본 폴더 경로
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

            # 매물 번호 추출
            try:
                id_element = page.locator(
                    '#sidebar-content > div.sidebar-content > div.badge-wrapper > div:nth-child(1) > div.house-index > span'
                )
                if id_element.is_visible():
                    property_id = id_element.inner_text().strip()
            except Exception:
                pass

            # 기본 정보 테이블
            rows = page.locator('div.detail-table-row').all()
            for row in rows:
                try:
                    key = row.locator('div.detail-table-th').inner_text().strip()
                    value = row.locator('div.detail-table-td').inner_text().strip()
                    if key and value:
                        room_info[key] = value
                except:
                    continue

            # 추가 옵션
            options = [el.inner_text().strip()
                       for el in page.locator('div.detail-option-table dd').all()
                       if el.is_visible()]
            if options:
                room_info['추가옵션'] = options

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
    base_dir = "scraped_data"
    info_dir = os.path.join(base_dir, "info")
    os.makedirs(info_dir, exist_ok=True)

    # ✅ 여기에 여러 매물 URL 넣기
    urls_to_scrape = [
        "https://www.peterpanz.com/house/17932726",
        "https://www.peterpanz.com/house/17933491",
        "https://www.peterpanz.com/house/17930111"
    ]

    for url in urls_to_scrape:
        data, pid = scrape_peterpan_room_info(url, base_dir)
        if not pid:
            print(f"⚠️ {url} → 매물 ID를 찾지 못해 JSON 저장 건너뜀")
            continue

        # JSON 파일 저장
        file_path = os.path.join(info_dir, f"{pid}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 저장 완료: {file_path}")


if __name__ == "__main__":
    main()
