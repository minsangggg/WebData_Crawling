import asyncio
from playwright.async_api import async_playwright
import json
import pymysql
import os
import requests
from urllib.parse import urlparse, urljoin
from pathlib import Path

# 데이터베이스 컬럼 매핑
COLUMN_MAPPING = {
    "거래방식": "transaction_type",        # 거래방식
    "관리비": "management_fee",          # 관리비
    "융자금": "loan_amount",             # 융자금
    "입주가능일": "move_in_date",            # 입주가능일
    "전입신고 여부": "residence_report",        # 전입신고 여부
    "건축물용도": "building_usage",          # 건축물용도
    "건물형태": "building_type",           # 건물형태
    "전용면적": "exclusive_area",          # 전용면적
    "해당층/전체층": "floor_info",              # 해당층/전체층
    "방/욕실개수": "room_bathroom_count",    # 방/욕실개수
    "방거실형태": "room_living_type",       # 방거실형태
    "주실기준/방향": "main_room_direction",    # 주실기준/방향
    "현관유형": "entrance_type",          # 현관유형
    "총주차대수": "total_parking_spaces",   # 총주차대수
    "주차": "parking_info",           # 주차
    "위반건축물 여부": "illegal_building",       # 위반건축물 여부
    "준공인가일": "completion_date",        # 준공인가일
    "난방방식": "heating_system",         # 난방방식
    "냉방시설": "cooling_system",         # 냉방시설
    "생활시설": "living_facilities",      # 생활시설
    "보안시설": "security_facilities",    # 보안시설
    "기타시설": "other_facilities",       # 기타시설
    "추가옵션": "additional_options", # 추가옵션
    "매물주소": "property_address",        # 매물주소
    "오피스텔명" : "building_name",
    "건물명":"building_name"



}

# 스크래핑할 CSS 셀렉터들
selectors = [
    "#single-content > div.detail > div.detail-table > div:nth-child(2) > div:nth-child(1) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div:nth-child(2) > div:nth-child(2) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div:nth-child(2) > div:nth-child(3) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div:nth-child(2) > div:nth-child(4) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div:nth-child(2) > div:nth-child(5) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(1) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(2) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(3) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(4) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(5) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(6) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(7) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(8) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(9) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(10) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(11) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div.detail-table-wrapper.-noBorderTop > div:nth-child(12) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table-wrapper > div:nth-child(1) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table-wrapper > div:nth-child(2) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table-wrapper > div:nth-child(3) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table-wrapper > div:nth-child(4) > div.detail-table-td",
    "#single-content > div.detail > div.detail-table > div:nth-child(2) > div:nth-child(2) > div.detail-table-td > div.td-text-small.mt-16.text-caption",
    "#single-content > div.detail > div:nth-child(10) > div:nth-child(1) > div > div > div:nth-child(1) > span.address"
]

# 옵션 테이블 셀렉터들
option_selectors = [
    "#single-content > div.detail > div.detail-option-table > dl:nth-child(1) > dd",
    "#single-content > div.detail > div.detail-option-table > dl:nth-child(2) > dd"
]

def get_pending_urls(db_config):
    """대기 중인 URL들을 가져옵니다."""
    connection = None
    try:
        connection = pymysql.connect(**db_config, charset='utf8mb4', use_unicode=True)
        cursor = connection.cursor(pymysql.cursors.DictCursor)
        
        query = "SELECT id, property_url, area FROM target_urls WHERE status = 'pending' ORDER BY created_at ASC"
        cursor.execute(query)
        results = cursor.fetchall()
        
        print(f"대기 중인 URL: {len(results)}개")
        return results
        
    except Exception as e:
        print(f"URL 조회 오류: {str(e)}")
        return []
    finally:
        if connection:
            connection.close()

def update_url_status(url_id, status, db_config):
    """URL 상태 업데이트"""
    connection = None
    try:
        connection = pymysql.connect(**db_config, charset='utf8mb4', use_unicode=True)
        cursor = connection.cursor()
        
        cursor.execute("UPDATE target_urls SET status = %s WHERE id = %s", (status, url_id))
        connection.commit()
        
    except Exception as e:
        print(f"상태 업데이트 오류: {str(e)}")
    finally:
        if connection:
            connection.close()

async def scrape_property_with_images(property_url, url_id, area, db_config, save_images=True):
    """매물 정보와 이미지를 스크래핑"""
    
    # 상태를 processing으로 변경
    update_url_status(url_id, 'processing', db_config)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        page = await context.new_page()
        
        try:
            print(f"\n처리 중: {property_url}")
            
            # 페이지 로드
            await page.goto(property_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            scraped_data = {}
            db_data = {}
            
            # 매물 정보 추출
            for i, selector in enumerate(selectors, 1):
                try:
                    element = await page.query_selector(selector)
                    
                    if element:
                        text_content = await element.inner_text()
                        text_content = text_content.strip()
                        
                        if text_content:
                            data_key = f"data_{i}"
                            scraped_data[data_key] = text_content
                            
                            if data_key in COLUMN_MAPPING:
                                db_column = COLUMN_MAPPING[data_key]
                                db_data[db_column] = text_content
                                
                except Exception as e:
                    continue
            
            # 옵션 데이터 추출
            option_data = []
            for selector in option_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element:
                        text_content = await element.inner_text()
                        text_content = text_content.strip()
                        if text_content:
                            option_data.append(text_content)
                except Exception as e:
                    continue
            
            if option_data:
                scraped_data["option_table"] = option_data
                db_data["additional_options"] = json.dumps(option_data, ensure_ascii=False)
            
            # area는 room 테이블에 컬럼이 없으므로 제거
            
            print(f"매물 정보 추출 완료: {len(db_data)}개 항목")
            
            # 이미지 스크래핑
            image_paths = []
            if save_images:
                image_paths = await scrape_images(page, property_url)
                print(f"이미지 저장: {len(image_paths)}개")
            
            # 데이터베이스에 저장
            room_id = insert_to_database(db_data, property_url, db_config)
            
            if room_id and image_paths:
                insert_images_to_database(room_id, image_paths, db_config)
            
            if room_id:
                update_url_status(url_id, 'completed', db_config)
                print(f"✓ 완료: room_id {room_id}")
                return True
            else:
                update_url_status(url_id, 'failed', db_config)
                return False
                
        except Exception as e:
            print(f"✗ 오류: {str(e)}")
            update_url_status(url_id, 'failed', db_config)
            return False
            
        finally:
            await browser.close()

async def scrape_images(page, property_url, base_save_dir="images/properties"):
    """이미지 스크래핑"""
    property_id = property_url.split('/')[-1]
    save_dir = Path(base_save_dir)
    save_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        image_selector = "#photoCarousel > div.carousel-inner img"
        image_elements = await page.query_selector_all(image_selector)
        
        if not image_elements:
            return []
        
        saved_paths = []
        
        for idx, img_element in enumerate(image_elements, 1):
            try:
                img_src = await img_element.get_attribute('src')
                if not img_src:
                    img_src = await img_element.get_attribute('data-src')
                
                if not img_src:
                    continue
                
                # URL 정규화
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif img_src.startswith('/'):
                    base_url = f"https://{urlparse(property_url).netloc}"
                    img_src = urljoin(base_url, img_src)
                
                # 파일명 생성
                file_ext = Path(urlparse(img_src).path).suffix.lower() or '.jpg'
                filename = f"{property_id}_{idx:02d}{file_ext}"
                file_path = save_dir / filename
                
                # 이미지 다운로드
                if await download_image(img_src, file_path):
                    relative_path = f"{base_save_dir}/{filename}"
                    saved_paths.append({
                        'path': relative_path,
                        'order': idx,
                        'is_thumbnail': (idx == 1)
                    })
                
            except Exception as e:
                continue
        
        return saved_paths
        
    except Exception as e:
        return []

async def download_image(img_url, file_path, timeout=30):
    """이미지 다운로드"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.peterpanz.com/'
        }
        
        response = requests.get(img_url, headers=headers, timeout=timeout, stream=True)
        response.raise_for_status()
        
        if int(response.headers.get('content-length', 0)) < 1000:
            return False
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
        
    except Exception as e:
        return False

def insert_to_database(db_data, property_url, db_config):
    """매물 정보를 데이터베이스에 저장"""
    connection = None
    try:
        connection = pymysql.connect(**db_config, charset='utf8mb4', use_unicode=True, autocommit=False)
        cursor = connection.cursor()
        cursor.execute("SET NAMES utf8mb4")
        
        db_data['property_url'] = property_url
        
        columns = list(db_data.keys())
        placeholders = ', '.join(['%s'] * len(columns))
        column_names = ', '.join(columns)
        
        insert_query = f"""
        INSERT INTO room ({column_names}) 
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE
        """
        
        update_parts = []
        for col in columns:
            if col != 'property_url':
                update_parts.append(f"{col} = VALUES({col})")
        
        insert_query += ', '.join(update_parts)
        
        values = [db_data[col] for col in columns]
        cursor.execute(insert_query, values)
        
        room_id = cursor.lastrowid
        if not room_id:
            cursor.execute("SELECT id FROM room WHERE property_url = %s", (property_url,))
            room_id = cursor.fetchone()[0]
        
        connection.commit()
        
        return room_id
        
    except Exception as e:
        print(f"DB 저장 오류: {str(e)}")
        if connection:
            connection.rollback()
        return None
        
    finally:
        if connection:
            connection.close()

def insert_images_to_database(room_id, image_data_list, db_config):
    """이미지 정보를 데이터베이스에 저장"""
    if not image_data_list:
        return
    
    connection = None
    try:
        connection = pymysql.connect(**db_config, charset='utf8mb4', use_unicode=True, autocommit=False)
        cursor = connection.cursor()
        cursor.execute("SET NAMES utf8mb4")
        
        cursor.execute("DELETE FROM images WHERE property_id = %s", (room_id,))
        
        insert_query = """
        INSERT INTO images (property_id, image_path, image_order, is_thumbnail)
        VALUES (%s, %s, %s, %s)
        """
        
        for img_data in image_data_list:
            cursor.execute(insert_query, (
                room_id,
                img_data['path'],
                img_data['order'],
                img_data['is_thumbnail']
            ))
        
        connection.commit()
        
    except Exception as e:
        print(f"이미지 저장 오류: {str(e)}")
        if connection:
            connection.rollback()
    
    finally:
        if connection:
            connection.close()

async def main():
    """메인 실행 함수 - DB에서 URL 불러와서 자동 처리"""
    
    # 데이터베이스 설정
    db_config = {
        'host': 'localhost',
        'port': 3310,
        'user': 'root',
        'password': '1234',
        'database': 'cp_data'
    }
    
    print("=== 자동 매물 스크래핑 시작 ===")
    
    # DB에서 대기 중인 URL들 가져오기
    pending_urls = get_pending_urls(db_config)
    
    if not pending_urls:
        print("처리할 URL이 없습니다.")
        return
    
    success_count = 0
    fail_count = 0
    
    # 각 URL 처리
    for url_data in pending_urls:
        url_id = url_data['id']
        property_url = url_data['property_url']
        area = url_data.get('area')
        
        print(f"\n[{success_count + fail_count + 1}/{len(pending_urls)}] 처리 중...")
        
        result = await scrape_property_with_images(
            property_url=property_url,
            url_id=url_id,
            area=area,
            db_config=db_config,
            save_images=True
        )
        
        if result:
            success_count += 1
        else:
            fail_count += 1
        
        # 요청 간 딜레이
        await asyncio.sleep(2)
    
    print(f"\n=== 완료 ===")
    print(f"성공: {success_count}개")
    print(f"실패: {fail_count}개")

if __name__ == "__main__":
    asyncio.run(main())