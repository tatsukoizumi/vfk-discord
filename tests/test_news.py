from pathlib import Path

from vfk_discord.news import NewsItem, parse_news_html

FIXTURE = Path(__file__).parent / "fixtures" / "news_match.html"
INDEX_URL = "https://www.ventforet.jp/news/match"


def test_parse_news_html() -> None:
    items = parse_news_html(FIXTURE.read_bytes(), INDEX_URL)
    assert items == [
        NewsItem(
            id="20260902_02",
            url="https://www.ventforet.jp/news/match/20260902_02",
            title="9月5日（土）山形戦 チケット完売のお知らせ",
            image="https://cdn.www.ventforet.jp/system/news_images/20260902_02.jpg",
        ),
        NewsItem(
            id="20260902_01",
            url="https://www.ventforet.jp/news/match/20260902_01",
            title="9月2日（水）FC大阪戦 イベント情報",
            image="https://cdn.www.ventforet.jp/system/news_images/20260902_01.jpg",
        ),
        NewsItem(
            id="20260901_01",
            url="https://www.ventforet.jp/news/match/20260901_01",
            title="ファンクラブ会員限定イベントのご案内",
            image="https://cdn.www.ventforet.jp/system/news_images/20260901_01.jpg",
        ),
    ]


def test_parse_news_html_empty_page() -> None:
    assert parse_news_html("<html><body></body></html>", INDEX_URL) == []
