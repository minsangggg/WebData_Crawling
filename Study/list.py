import asyncio
from playwright.async_api import async_playwright
import pymysql
import re
from urllib.parse import urljoin

class SimpleURLCollector:
    def __init__(self, db_config):
        self.db_config = db_config
        self.base_url = "https://www.peterpanz.com"
        
    async def collect_urls(self, list_page_url, area_name, max_items=50):
        """
        리스트 페이지에서 매물 URL들을 수집하고 DB에 저장
        """
        print(f"=== {area_name} URL 수집 시작 ===")
        print(f"목표: {max_items}개 URL")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )
            page = await context.new_page()
            
            try:
                # 페이지 로드
                print("페이지 로딩 중...")
                await page.goto(list_page_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(5000)
                
                # --- [수정된 부분 시작] ---
                print("페이지 스크롤 시작 (10초간)...")
                
                # 스크롤 대상 요소 선택
                scrollable_element_selector = "#mainPanelWrapper > div > div"
                scrollable_element = await page.query_selector(scrollable_element_selector)

                if scrollable_element:
                    scroll_start_time = asyncio.get_event_loop().time()
                    while asyncio.get_event_loop().time() - scroll_start_time < 60:
                        # 스크롤 가능한 요소의 가장 아래로 스크롤
                        await scrollable_element.evaluate("el => el.scrollTop = el.scrollHeight")
                        # 새로운 내용이 로드되기를 기다림
                        await asyncio.sleep(1) # 1초 간격으로 스크롤
                    
                    print("✓ 스크롤 완료")
                else:
                    print("✗ 스크롤 대상 요소를 찾을 수 없습니다.")

                
                # URL 수집
                urls = await self.find_property_urls(page, max_items)
                
                # DB에 저장
                if urls:
                    saved_count = self.save_to_database(urls, area_name, list_page_url)
                    print(f"✓ {saved_count}개 URL이 DB에 저장됨")
                else:
                    print("✗ 수집된 URL이 없습니다")
                
                return urls
                
            finally:
                await browser.close()
    
    async def find_property_urls(self, page, max_items):
        """페이지에서 매물 URL들 찾기"""
        urls = []
        
        # 방법 1: 실제 HTML 구조에 맞는 셀렉터들
        selectors = [
            # Vue.js 컴포넌트 기반 셀렉터들
            ".recommended-real-estate-list-item__wrapper > div",
            ".recommended-real-estate-list-item__wrapper",
            ".a-house",
            "[data-hidx]",  # 매물 ID가 있는 속성
            "[data-gtag*='detail']",
            ".recommend-real-estate-item-house__wrapper",
            
            # 기존 시도했던 셀렉터들
            ".recommended-house-list-item__wrapper",
            "#mainPanelWrapper .recommended-house-list-item__wrapper"
        ]
        
        for selector in selectors:
            try:
                elements = await page.query_selector_all(selector)
                if elements:
                    print(f"✓ {len(elements)}개 요소 발견 (셀렉터: {selector})")
                    
                    # 디버깅: 첫 번째 요소 분석
                    if elements:
                        first_element = elements[0]
                        print("디버깅 - 첫 번째 요소 분석:")
                        
                        # data-hidx 속성 확인 (매물 ID)
                        hidx = await first_element.get_attribute('data-hidx')
                        print(f"  data-hidx: {hidx}")
                        
                        # data-gtag 속성 확인
                        gtag = await first_element.get_attribute('data-gtag')
                        print(f"  data-gtag: {gtag}")
                        
                        # 모든 data- 속성 확인
                        data_attrs = await first_element.evaluate('''
                            el => {
                                const attrs = {};
                                for (let attr of el.attributes) {
                                    if (attr.name.startsWith('data-')) {
                                        attrs[attr.name] = attr.value;
                                    }
                                }
                                return attrs;
                            }
                        ''')
                        print(f"  data 속성들: {data_attrs}")
                    
                    # URL 추출 시도 (data-hidx 우선)
                    found_urls = []
                    for i, element in enumerate(elements[:max_items]):
                        url = await self.extract_url_from_vue_component(element)
                        if url and url not in found_urls:
                            found_urls.append(url)
                            print(f"  ✓ [{len(found_urls)}] {url}")
                        elif i < 5:
                            print(f"  [X] 요소 {i+1}: URL 추출 실패")
                    
                    if found_urls:
                        urls = found_urls
                        break
                        
            except Exception as e:
                print(f"셀렉터 {selector} 오류: {str(e)}")
                continue
        
        # 방법 2: data-hidx로 직접 검색
        if not urls:
            print("data-hidx 속성으로 직접 검색...")
            urls = await self.search_by_data_hidx(page, max_items)
        
        # 방법 3: JavaScript로 더 적극적으로 찾기
        if not urls:
            print("JavaScript로 더 적극적 재시도...")
            urls = await self.aggressive_javascript_search(page, max_items)
        
        return urls
    
    async def extract_url_from_vue_component(self, element):
        """Vue.js 컴포넌트에서 URL 추출"""
        try:
            # 방법 1: data-hidx 속성에서 매물 ID 추출
            hidx = await element.get_attribute('data-hidx')
            if hidx and hidx.isdigit():
                return f"{self.base_url}/house/{hidx}"
            
            # 방법 2: data-gtag에서 정보 추출
            gtag = await element.get_attribute('data-gtag')
            if gtag and 'detail' in gtag:
                # 부모나 자식에서 hidx 찾기
                parent = await element.evaluate('el => el.closest("[data-hidx]")')
                if parent:
                    parent_hidx = await parent.get_attribute('data-hidx')
                    if parent_hidx and parent_hidx.isdigit():
                        return f"{self.base_url}/house/{parent_hidx}"
            
            # 방법 3: 기존 방법들도 시도
            return await self.extract_url(element)
            
        except Exception as e:
            return None
    
    async def search_by_data_hidx(self, page, max_items):
        """data-hidx 속성을 가진 요소들을 직접 찾기"""
        try:
            elements = await page.query_selector_all('[data-hidx]')
            if not elements:
                return []
            
            print(f"✓ data-hidx로 {len(elements)}개 매물 발견")
            
            urls = []
            for element in elements[:max_items]:
                hidx = await element.get_attribute('data-hidx')
                if hidx and hidx.isdigit() and len(hidx) >= 5:
                    url = f"{self.base_url}/house/{hidx}"
                    urls.append(url)
                    print(f"  [{len(urls)}] {url}")
            
            return urls
            
        except Exception as e:
            print(f"data-hidx 검색 실패: {str(e)}")
            return []
    
    async def aggressive_javascript_search(self, page, max_items):
        """JavaScript로 더 적극적으로 URL 찾기"""
        try:
            urls = await page.evaluate(f"""
                () => {{
                    const urls = new Set();
                    
                    // 1. 모든 링크에서 /house/ 패턴 찾기
                    document.querySelectorAll('a[href]').forEach(link => {{
                        const href = link.getAttribute('href');
                        if (href && href.includes('/house/')) {{
                            const fullUrl = href.startsWith('/') ? 
                                'https://www.peterpanz.com' + href : href;
                            urls.add(fullUrl);
                        }}
                    }});
                    
                    // 2. onclick 속성에서 찾기
                    document.querySelectorAll('[onclick]').forEach(el => {{
                        const onclick = el.getAttribute('onclick');
                        if (onclick && onclick.includes('house')) {{
                            const match = onclick.match(/\\/house\\/(\\d+)/);
                            if (match) {{
                                urls.add('https://www.peterpanz.com/house/' + match[1]);
                            }}
                        }}
                    }});
                    
                    // 3. 모든 클릭 이벤트가 있는 요소 확인
                    document.querySelectorAll('*').forEach(el => {{
                        // Vue.js 이벤트 핸들러 확인
                        if (el.__vue__ || el._vnode) {{
                            console.log('Vue component found');
                        }}
                        
                        // data 속성들 확인
                        ['data-href', 'data-url', 'data-link', 'data-house-id', 'data-id'].forEach(attr => {{
                            const value = el.getAttribute(attr);
                            if (value) {{
                                if (value.includes('/house/')) {{
                                    urls.add(value.startsWith('/') ? 'https://www.peterpanz.com' + value : value);
                                }} else if (/^\\d+$/.test(value) && value.length >= 5) {{
                                    urls.add('https://www.peterpanz.com/house/' + value);
                                }}
                            }}
                        }});
                    }});
                    
                    // 4. 페이지의 모든 텍스트에서 /house/숫자 패턴 찾기
                    const pageText = document.documentElement.outerHTML;
                    const matches = pageText.match(/\\/house\\/(\\d{{5,}})/g);
                    if (matches) {{
                        matches.forEach(match => {{
                            urls.add('https://www.peterpanz.com' + match);
                        }});
                    }}
                    
                    console.log('Found URLs:', Array.from(urls));
                    return Array.from(urls).slice(0, {max_items});
                }}
            """)
            
            if urls:
                print(f"✓ 적극적 JavaScript 검색으로 {len(urls)}개 URL 발견")
                for i, url in enumerate(urls, 1):
                    print(f"  [{i}] {url}")
            else:
                print("✗ 적극적 JavaScript 검색에서도 URL을 찾지 못함")
            
            return urls
            
        except Exception as e:
            print(f"적극적 JavaScript 검색 실패: {str(e)}")
            return []
    
    async def regex_search(self, page, max_items):
        """정규식으로 페이지 소스에서 URL 찾기"""
        try:
            html_content = await page.content()
            
            # 다양한 패턴으로 매물 ID 찾기
            patterns = [
                r'/house/(\d+)',
                r'house/(\d+)', 
                r'"houseId"\s*:\s*"?(\d+)"?',
                r'"house_id"\s*:\s*"?(\d+)"?',
                r'"id"\s*:\s*"?(\d+)"?.*house',
                r'house.*"id"\s*:\s*"?(\d+)"?'
            ]
            
            house_ids = set()
            
            for pattern in patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                for match in matches:
                    if match.isdigit() and len(match) >= 5:  # 5자리 이상인 ID만
                        house_ids.add(match)
            
            urls = [f"{self.base_url}/house/{house_id}" for house_id in house_ids]
            urls = urls[:max_items]
            
            if urls:
                print(f"✓ 정규식으로 {len(urls)}개 URL 발견")
                for i, url in enumerate(urls[:5], 1):  # 처음 5개만 출력
                    print(f"  [{i}] {url}")
                if len(urls) > 5:
                    print(f"  ... 외 {len(urls) - 5}개 더")
            
            return urls
            
        except Exception as e:
            print(f"정규식 검색 실패: {str(e)}")
            return []
    
    def save_to_database(self, urls, area_name, source_page):
        """URL들을 데이터베이스에 저장"""
        connection = None
        try:
            connection = pymysql.connect(**self.db_config, charset='utf8mb4')
            cursor = connection.cursor()
            
            # URL들 삽입
            insert_query = """
            INSERT IGNORE INTO target_urls (property_url, area, source_page) 
            VALUES (%s, %s, %s)
            """
            
            data = [(url, area_name, source_page) for url in urls]
            cursor.executemany(insert_query, data)
            
            inserted_count = cursor.rowcount
            connection.commit()
            
            return inserted_count
            
        except Exception as e:
            print(f"DB 저장 오류: {str(e)}")
            return 0
            
        finally:
            if connection:
                connection.close()

async def main():
    # 데이터베이스 설정
    db_config = {
        'host': 'localhost',
        'port': 3310,
        'user': 'root',
        'password': '1234',  # 실제 비밀번호 입력
        'database': 'bangu'
    }
    
    # URL 수집기 생성
    collector = SimpleURLCollector(db_config)
    
    # 도림동 매물 URL 수집
    list_page_url = 'https://www.peterpanz.com/onetworoom?zoomLevel=13&center=%7B"y":37.5457364,"_lat":37.5457364,"x":126.9586473,"_lng":126.9586473%7D&dong=&gungu=&filter=latitude:37.4898445~37.6015864%7C%7Clongitude:126.9397646~127.0736604%7C%7CcheckMonth:999~999%7C%7CcontractType;%5B"월세"%5D%7C%7CroomCount_etc;%5B"6층~9층","1층","2층~5층","10층%20이상","반지층/지하","옥탑"%5D%7C%7CisManagerFee;%5B"add"%5D%7C%7CbuildingType;%5B"원/투룸"%5D&'
    
    try:
        # URL 수집 실행
        urls = await collector.collect_urls(
            list_page_url=list_page_url,
            area_name="도림동",
            max_items=1000
        )
        
        print(f"\n=== 완료 ===")
        print(f"수집된 URL: {len(urls)}개")
        
    except Exception as e:
        print(f"실행 오류: {str(e)}")

if __name__ == "__main__":
    print("=== 간단한 URL 수집기 ===")
    print("도림동 매물 URL을 수집해서 DB에 저장합니다.")
    print()
    print("사전 준비:")
    print("1. target_urls 테이블이 먼저 생성되어 있어야 합니다")
    print("2. db_config에서 password 입력")
    print("3. cp_data 데이터베이스 존재 확인")
    print()
    
    asyncio.run(main())