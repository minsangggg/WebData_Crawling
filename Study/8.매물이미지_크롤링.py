from playwright.sync_api import sync_playwright
import time
import re
import requests
import os

def scrape_zigbang_room_info():
    """직방 특정 매물의 정보를 구조적으로 스크래핑합니다."""
    
    # 스크래핑할 URL (유저가 제공한 URL)
    url = "https://www.zigbang.com/home/oneroom/items/45991434?itemDetailType=ZIGBANG&imageThumbnail=https%3A%2F%2Fic.zigbang.com%2Fic%2Fitems%2F45991434%2F1.jpg&hasVrKey=false"
    
    with sync_playwright() as p:
        # 브라우저 시작 (User-Agent를 추가하여 봇 감지 우회 시도)
        browser = p.chromium.launch(
            headless=False,
            args=['--no-sandbox', '--disable-blink-features=AutomationControlled']
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        try:
            print("➡️ 페이지에 접속하는 중...")
            page.goto(url, wait_until='domcontentloaded', timeout=30000)
            
            # 페이지 로딩을 위해 충분한 시간 대기
            print("⏳ 페이지 로딩을 위해 5초 대기...")
            time.sleep(5)
            
            # 현재 페이지의 제목을 확인하여 접속 성공 여부 판단
            page_title = page.title()
            print(f"✅ 페이지 제목: {page_title}")
            
           
            button4_selector = 'div.css-1dbjc4n.r-13awgt0 > div.css-1dbjc4n.r-13awgt0 > div.css-1dbjc4n.r-14lw9ot.r-13awgt0 > div > div > div:nth-child(1) > div > div > div > div.css-1dbjc4n.r-13awgt0.r-18u37iz.r-1udh08x > div:nth-child(2) > div > div.css-1dbjc4n.r-1pi2tsx.r-u8s1d.r-13qz1uu'

            try:
                print("➡️ 네 번째 버튼을 클릭합니다...")
                page.locator(button4_selector).first.click(timeout=10000)
                print("✅ 네 번째 버튼 클릭 완료. 2초 대기.")
                time.sleep(2)
            except Exception as e:
                print(f"❌ 버튼 클릭 중 오류 발생: {e}")
                
            # 이미지 목록을 찾고 저장하는 로직 추가
            image_selector = 'img[src*="items/"]'
            
            print("\n====================================")
            print("🖼️ 이미지 목록 추출 및 저장")
            print("====================================")
            
            image_elements = page.query_selector_all(image_selector)
            excluded_pattern = re.compile(r'w=(400|800)&h=(300|600)')
            
            if not os.path.exists("./img"):
                os.makedirs("./img")
            
            if image_elements:
                filtered_images = []
                for img_elem in image_elements:
                    img_url = img_elem.get_attribute('src')
                    if img_url and re.search(r'items/', img_url):
                        # 제외 패턴에 해당하는 URL은 건너뜁니다.
                        if not excluded_pattern.search(img_url):
                            filtered_images.append(img_url)

                if filtered_images:
                    print(f"✅ 총 {len(filtered_images)}개의 이미지를 다운로드합니다.")
                    for i, img_url in enumerate(filtered_images, 1):
                        if i <= 3:
                            continue
                        try:
                            img_data = requests.get(img_url).content
                            img_path = f"./img/image_{i}.jpg"
                            with open(img_path, 'wb') as handler:
                                handler.write(img_data)
                            print(f"✅ 이미지 {i} 저장 완료: {img_path}")
                        except Exception as e:
                            print(f"❌ 이미지 다운로드 및 저장 중 오류 발생: {e}")
                else:
                    print("❌ 필터링 조건을 만족하는 이미지 요소를 찾을 수 없습니다.")
            else:
                print("❌ 요청하신 선택자로 이미지 요소를 찾을 수 없습니다.")

        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}")
            page.screenshot(path='error_screenshot.png')
            print("📸 오류 스크린샷이 error_screenshot.png로 저장되었습니다.")
            
        finally:
            browser.close()

if __name__ == "__main__":
    scrape_zigbang_room_info()