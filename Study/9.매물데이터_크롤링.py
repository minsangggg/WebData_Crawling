from playwright.sync_api import sync_playwright
import time
import re

def scrape_zigbang_room_info():
    """직방 특정 매물의 정보를 구조적으로 스크래핑합니다."""
    
    # 스크래핑할 URL (유저가 제공한 URL)
    url = "https://www.zigbang.com/home/oneroom/items/45998569?itemDetailType=ZIGBANG&imageThumbnail=https%3A%2F%2Fic.zigbang.com%2Fic%2Fitems%2F45998569%2F1.jpg&hasVrKey=false"
    
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
            
            # '더보기' 버튼을 찾아 클릭하는 로직
            more_button_selector = 'text="더보기"'
            more_button = page.locator(more_button_selector).first
            
            if more_button.is_visible(timeout=5000):
                print("➡️ '더보기' 버튼을 클릭합니다...")
                more_button.click()
                print("✅ '더보기' 버튼 클릭 완료. 추가 정보 로딩을 위해 2초 대기.")
                time.sleep(2)  # 클릭 후 콘텐츠 로딩 대기
            else:
                print("ℹ️ '더보기' 버튼이 없습니다. 다음 단계로 넘어갑니다.")

            # '더보기' 클릭 후 바로 나타나는 목록의 데이터 가져오기
            first_detail_selector = 'div:nth-child(2) > div:nth-child(2) > div > div.css-1dbjc4n.r-150rngu.r-14lw9ot.r-eqz5dr.r-16y2uox.r-1wbh5a2.r-11yh6sk.r-1rnoaur.r-1sncvnh > div'
            
            print("\n====================================")
            print("🔍 '더보기' 클릭 후 첫 번째 목록 추출")
            print("====================================")
            
            first_detail_elements = page.query_selector_all(first_detail_selector)
            
            if first_detail_elements:
                print(f"✅ {len(first_detail_elements)}개의 요소를 찾았습니다.")
                for i, elem in enumerate(first_detail_elements, 1):
                    try:
                        print(f"--- 요소 [{i}] ---")
                        print(elem.inner_text())
                    except Exception as e:
                        print(f"❌ 텍스트 추출 중 오류 발생: {e}")
            else:
                print("❌ 첫 번째 목록 요소를 찾을 수 없습니다.")

            # 첫 번째 버튼 클릭 (클릭 가능할 때까지 기다리도록 수정)
            button1_selector = '#animatedComponent > div > svg'
            button1 = page.locator(button1_selector).first
            try:
                print("➡️ 첫 번째 버튼을 클릭합니다...")
                button1.click(timeout=10000) # 버튼이 클릭 가능해질 때까지 최대 10초 대기
                print("✅ 첫 번째 버튼 클릭 완료. 다음 정보 로딩을 위해 2초 대기.")
                time.sleep(2)
            except Exception as e:
                print(f"❌ 첫 번째 버튼을 클릭하는 중 오류가 발생했습니다: {e}")

            # 두 번째 버튼 클릭
            button2_selector = 'div.css-1dbjc4n.r-13awgt0 > div.css-1dbjc4n.r-13awgt0 > div.css-1dbjc4n.r-14lw9ot.r-13awgt0 > div > div > div:nth-child(6) > div.css-1dbjc4n.r-18u37iz.r-1ah4tor > div.css-1dbjc4n.r-1awozwy.r-18u37iz.r-17s6mgv.r-5oul0u.r-1joea0r.r-knv0ih > div'
            button2 = page.locator(button2_selector).first
            try:
                print("➡️ 두 번째 버튼을 클릭합니다...")
                button2.click(timeout=10000) # 버튼이 클릭 가능해질 때까지 최대 10초 대기
                print("✅ 두 번째 버튼 클릭 완료. 다음 정보 로딩을 위해 2초 대기.")
                time.sleep(2)
            except Exception as e:
                print(f"❌ 두 번째 버튼을 클릭하는 중 오류가 발생했습니다: {e}")

            # 최종 목록의 데이터 가져오기
            final_detail_selector = 'div.css-1dbjc4n.r-150rngu.r-14lw9ot.r-eqz5dr.r-16y2uox.r-1wbh5a2.r-11yh6sk.r-1rnoaur.r-1sncvnh > div'
            
            print("\n====================================")
            print("🔍 최종적으로 요청하신 목록 추출")
            print("====================================")
            
            final_detail_elements = page.query_selector_all(final_detail_selector)
            
            if final_detail_elements:
                print(f"✅ {len(final_detail_elements)}개의 요소를 찾았습니다.")
                for i, elem in enumerate(final_detail_elements, 1):
                    try:
                        print(f"--- 요소 [{i}] ---")
                        print(elem.inner_text())
                    except Exception as e:
                        print(f"❌ 텍스트 추출 중 오류 발생: {e}")
            else:
                print("❌ 최종 목록 요소를 찾을 수 없습니다.")

        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}")
            page.screenshot(path='error_screenshot.png')
            print("📸 오류 스크린샷이 error_screenshot.png로 저장되었습니다.")
            
        finally:
            browser.close()

if __name__ == "__main__":
    scrape_zigbang_room_info()