from typing import Optional

from app.clients.tei_embeddings import TeiEmbeddings
from app.conf.app_config import app_config, EmbeddingConfig


class EmbeddingClientManager:
    def __init__(self, config: EmbeddingConfig):
        self.embeddings: Optional[TeiEmbeddings] = None
        self.config = config

    def _get_url(self) -> str:
        return f"http://{self.config.host}:{self.config.port}"

    def init(self) -> None:
        self.embeddings = TeiEmbeddings(base_url=self._get_url())


embedding_client_manager = EmbeddingClientManager(app_config.embedding)
