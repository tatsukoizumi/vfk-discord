import logging
from dataclasses import dataclass
from enum import Enum

import requests
from bs4 import BeautifulSoup, Tag

from vfk_discord import discord
from vfk_discord.config import Settings
from vfk_discord.store import Store

logger = logging.getLogger(__name__)

TOP_URL = "https://www.ventforet.jp"
LOGO_URL = "https://cdn.www.ventforet.jp/system/images/club/95/original/27.png?1330092232"
AUTHOR_NAME = "ヴァンフォーレ甲府公式"


class NewsCategory(Enum):
    MATCH = "match"  # 試合・イベント
    TEAM = "team"  # チーム
    OTHER = "other"  # その他

    @property
    def index_url(self) -> str:
        return f"{TOP_URL}/news/{self.value}"


# カテゴリごとにチャンネルを分けたいので、チャンネルごとに Webhook を使い分ける
def _webhook_url(settings: Settings, category: NewsCategory) -> str:
    match category:
        case NewsCategory.MATCH:
            return settings.discord_webhook_url_match
        case NewsCategory.TEAM:
            return settings.discord_webhook_url_team
        case NewsCategory.OTHER:
            return settings.discord_webhook_url_other


@dataclass(frozen=True)
class NewsItem:
    id: str
    url: str
    title: str
    image: str


def parse_news_html(html: str | bytes, index_url: str) -> list[NewsItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: list[NewsItem] = []
    for element in soup.find_all("a", class_="newsList__item"):
        href = element.get("href")
        title_element = element.find(class_="top-news__information__detail")
        image_container = element.find(class_="newsList__itemImage")
        image = image_container.find("img") if isinstance(image_container, Tag) else None
        if not isinstance(href, str) or title_element is None or not isinstance(image, Tag):
            continue
        image_src = image.get("src")
        if not isinstance(image_src, str):
            continue
        news_id = href.split("/")[-1]
        items.append(
            NewsItem(
                id=news_id,
                url=f"{index_url}/{news_id}",
                title=title_element.get_text(),
                image=image_src,
            )
        )
    return items


def run(settings: Settings, store: Store) -> None:
    for category in NewsCategory:
        index_url = category.index_url
        response = requests.get(index_url, timeout=30)
        response.raise_for_status()
        items = parse_news_html(response.content, index_url)

        # 保存済みの最新 ID 以降（より新しいもの）だけを対象にする
        saved_latest_id = store.get_latest_news_id(category.name)
        new_items: list[NewsItem] = []
        for item in items:
            if item.id == saved_latest_id:
                break
            new_items.append(item)

        if not new_items:
            logger.info("no new items for %s", category.name)
            continue

        store.set_latest_news_id(category.name, new_items[0].id)

        # 古い順に送信する
        for item in reversed(new_items):
            logger.info("sending news %s: %s", item.id, item.title)
            discord.send_webhook_embed(
                _webhook_url(settings, category),
                author_name=AUTHOR_NAME,
                author_url=TOP_URL,
                author_icon_url=LOGO_URL,
                title=item.title,
                title_url=item.url,
                thumbnail_url=item.image,
            )
