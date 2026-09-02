from google.cloud import firestore


class Store:
    """Firestore への読み書き。クライアントはインスタンス生成時に作る（import 時に ADC を要求しない）。"""

    def __init__(self) -> None:
        self._db = firestore.Client()

    def get_latest_news_id(self, category_name: str) -> str:
        doc = self._db.collection("latest_news_id").document(category_name).get()
        if doc.exists:
            data = doc.to_dict()
            if data is not None:
                return str(data.get("id", ""))
        return ""

    def set_latest_news_id(self, category_name: str, news_id: str) -> None:
        self._db.collection("latest_news_id").document(category_name).set({"id": news_id})

    def match_thread_exists(self, key: str) -> bool:
        return bool(self._db.collection("match_threads").document(key).get().exists)

    def mark_match_thread(self, key: str, thread_id: str) -> None:
        self._db.collection("match_threads").document(key).set({"thread_id": thread_id})
