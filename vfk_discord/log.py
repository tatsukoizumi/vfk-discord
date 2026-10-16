import json
import logging


class CloudLoggingFormatter(logging.Formatter):
    """Cloud Logging の構造化ログ（1 行 JSON）として出力する。

    functions-framework は 1 行が JSON ならそれを payload として execution_id ラベルを足すので、
    severity を含めておけば Cloud Logging 上で重要度が付く。
    """

    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        if record.exc_info:
            message = f"{message}\n{self.formatException(record.exc_info)}"
        return json.dumps(
            {"severity": record.levelname, "message": message, "logger": record.name},
            ensure_ascii=False,
        )


def setup() -> None:
    root = logging.getLogger()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    # Cloud Functions は LOG_EXECUTION_ID=true を設定し、functions-framework がアプリの
    # 読み込み前にルートロガーを WARNING で構成するため、レベルを明示的に上げる
    root.setLevel(logging.INFO)
    for handler in root.handlers:
        handler.setFormatter(CloudLoggingFormatter())
