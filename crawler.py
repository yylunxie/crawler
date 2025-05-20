import urllib.parse
import json
import os
import time
import requests
from bs4 import BeautifulSoup


class Crawler:
    """
    A simple web crawler that extracts links from web pages.
    """

    def __init__(self, base_url, max_pages=10, delay=1):
        """
        Initialize the crawler.

        Args:
            base_url (str): The base URL to start crawling from
            max_pages (int): Maximum number of pages to crawl
            delay (int): Time to wait between requests in seconds
        """
        self.base_url = base_url
        self.max_pages = max_pages
        self.delay = delay
        self.visited_urls = set()
        self.pages_crawled = 0

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://tw.manhuagui.com/",
            "sec-ch-ua": '"Chromium";v="121", "Not A(Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "keep-alive",
        }

    def normalize_url(self, url, current_url):
        """Normalize relative URLs to absolute URLs."""
        return urllib.parse.urljoin(current_url, url)

    def get_page(self, url):
        """Fetch and parse a web page."""
        try:
            print(f"開始爬取: {url}")
            response = requests.get(
                url,
                headers=self.headers,
                timeout=15,
            )
            response.raise_for_status()

            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(response.text)

            return BeautifulSoup(response.text, "html.parser")
        except (requests.RequestException, ValueError) as e:
            print(f"Error fetching {url}: {e}")
            return None

    def extract_manga_info(self, soup):
        """Extract manga information from the page."""
        manga_list = []

        # 先檢查頁面結構
        print("檢查頁面結構...")
        print(f"頁面標題: {soup.title.text if soup.title else 'No title'}")

        # 根據HTML結構查找漫畫列表
        manga_items = soup.select("ul#contList > li")
        if not manga_items:
            print("沒有找到任何漫畫項目，請檢查網站結構或選擇器。")
            return manga_list

        print(f"找到漫畫項目數: {len(manga_items)}")

        for item in manga_items:
            try:
                # 根據實際的HTML結構提取資訊
                # 漫畫標題從 p.ell > a 中提取
                title_a = item.select_one("p.ell > a")
                # 漫畫連結
                link_a = item.select_one("a.bcover")
                # 封面圖片
                cover_img = item.select_one("a.bcover > img")
                # 話數在 a.bcover > span.tt 中
                chapter_span = item.select_one("a.bcover > span.tt")
                # 更新日期在 span.updateon 中
                update_span = item.select_one("span.updateon")
                # 評分在 span.updateon > em 中
                score_em = (
                    item.select_one("span.updateon > em") if update_span else None
                )

                if not title_a:
                    print(f"無法找到標題元素，跳過該項")
                    continue

                manga_title = title_a.text.strip()
                chapter_info = chapter_span.text.strip() if chapter_span else ""

                # 處理更新日期和評分
                update_date = ""
                score = ""
                if update_span:
                    update_text = update_span.text.strip()
                    if "更新於：" in update_text:
                        # 提取更新日期
                        parts = update_text.split("更新於：")
                        if len(parts) > 1:
                            date_part = parts[1].strip()
                            if score_em:
                                score = score_em.text.strip()
                                # 去除評分部分，只保留日期
                                date_part = date_part.replace(score, "").strip()
                            update_date = date_part

                manga = {
                    "title": manga_title,
                    "chapter": chapter_info,
                    "url": (
                        urllib.parse.urljoin(self.base_url, link_a["href"])
                        if link_a and link_a.get("href")
                        else ""
                    ),
                    "cover_img": (
                        cover_img["src"] if cover_img and cover_img.get("src") else ""
                    ),
                    "update_date": update_date,
                    "score": score,
                }
                manga_list.append(manga)
                print(
                    f"提取漫畫: {manga['title']} - {manga['chapter']} - {manga['update_date']}"
                )
            except Exception as e:
                print(f"Error extracting manga info: {e}")
                continue

        return manga_list

    def crawl(self):
        """Start crawling from the base URL."""

        # 確保資料夾存在
        os.makedirs("manga_data", exist_ok=True)

        # 開始爬蟲
        soup = self.get_page(self.base_url)
        if not soup:
            print("Failed to fetch the main page.")
            return

        # 提取漫畫資訊
        mangas = self.extract_manga_info(soup)
        print(f"Found {len(mangas)} manga on the main page.")

        # 儲存HTML用於檢查
        if len(mangas) == 0:
            print("網站結構可能有變化，請檢查debug_page.html檔案確認HTML結構。")
            return

        # 找尋分頁連結
        pagination_selectors = [
            "div.page-pagination a",
            "div.pager a",
            "div.pages a",
            "ul.pager a",
        ]
        pagination = []

        for selector in pagination_selectors:
            pagination = soup.select(selector)
            if pagination:
                print(f"找到分頁選擇器: {selector}")
                break

        page_links = []

        for link in pagination:
            if link.get("href") and "page=" in link["href"]:
                page_url = urllib.parse.urljoin(self.base_url, link["href"])
                if page_url not in self.visited_urls:
                    page_links.append(page_url)
        # 爬取其他分頁
        page_count = 1
        self.visited_urls.add(self.base_url)

        for page_url in page_links:
            if page_count >= self.max_pages:
                break

            time.sleep(self.delay)  # 尊重網站，避免頻繁請求
            soup = self.get_page(page_url)
            if not soup:
                continue

            page_mangas = self.extract_manga_info(soup)
            print(f"Found {len(page_mangas)} manga on page {page_count + 1}.")
            mangas.extend(page_mangas)

            self.visited_urls.add(page_url)
            page_count += 1

        # 儲存所有漫畫資訊到一個總檔案
        with open(
            os.path.join("manga_data", "all_manga.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(
                {
                    "total_manga": len(mangas),
                    "crawl_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "mangas": mangas,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

        print(f"Successfully crawled {len(mangas)} manga titles.")


if __name__ == "__main__":
    # Example usage
    crawler = Crawler("https://tw.manhuagui.com/list/view.html", max_pages=3)
    crawler.crawl()
