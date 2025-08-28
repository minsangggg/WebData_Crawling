# 10.최종크롤링.py
import requests
import time
from Insert_info import insert_room_info
from Pre_info import parse_room_info
from Pre_option import parse_options

# 페이지네이션 기반 크롤러
def crawl_peterpan(base_url, headers):
    all_items = []
    page = 1
    rows = 50   # 안정적으로 50개씩 요청

    while True:
        url = f"{base_url}&page={page}&rows={rows}"
        res = requests.get(url, headers=headers)

        if res.status_code != 200:
            print(f"❌ 요청 실패 (status {res.status_code})")
            break

        try:
            data = res.json()
        except Exception as e:
            print(f"❌ JSON 파싱 실패: {e}")
            break

        houses = []
        if "houses" in data:
            if "recommend" in data["houses"] and "image" in data["houses"]["recommend"]:
                houses.extend(data["houses"]["recommend"]["image"])
            if "withoutFee" in data["houses"] and "image" in data["houses"]["withoutFee"]:
                houses.extend(data["houses"]["withoutFee"]["image"])

        if not houses:
            print("⚠️ 더 이상 매물 없음. 종료")
            break

        print(f"✅ {page} 페이지 {len(houses)}건 수집 완료")
        all_items.extend(houses)

        total_count = data.get("totalCount", 0)
        if len(all_items) >= total_count:
            print(f"🎉 전체 {total_count}건 수집 완료")
            break

        page += 1
        time.sleep(1)

    return all_items


if __name__ == "__main__":
    base_url = "https://api.peterpanz.com/houses/area?zoomLevel=13&center=%7B%22y%22:37.5457364,%22_lat%22:37.5457364,%22x%22:126.9586473,%22_lng%22:126.9586473%7D&dong=&gungu=&filter=latitude:37.4898445~37.6015864%7C%7Clongitude:126.9397646~127.0736604%7C%7CcheckMonth:999~999%7C%7CcontractType;%5B%22%EC%9B%94%EC%84%B8%22%5D%7C%7CroomCount_etc;%5B%226%EC%B8%B5~9%EC%B8%B5%22,%221%EC%B8%B5%22,%222%EC%B8%B5~5%EC%B8%B5%22,%2210%EC%B8%B5%20%EC%9D%B4%EC%83%81%22,%22%EB%B0%98%EC%A7%80%EC%B8%B5/%EC%A7%80%ED%95%98%22,%22%EC%98%A5%ED%83%91%22%5D%7C%7CisManagerFee;%5B%22add%22%5D%7C%7CbuildingType;%5B%22%EC%9B%90/%ED%88%AC%EB%A3%B8%22%5D&&pageSize=10&pageIndex=1&search=&response_version=5.2&filter_version=5.1&order_by=random"
    headers = {"User-Agent": "Mozilla/5.0"}

    houses = crawl_peterpan(base_url, headers)

    # DB 적재
    for h in houses:
        try:
            room_data = parse_room_info(h)
            options = parse_options(h)
            images = [img["path"] for img in h.get("images", {}).get("S", [])]
            insert_room_info(room_data, options, images)
        except Exception as e:
            print(f"❌ DB 적재 중 오류: {e}")
