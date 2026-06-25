"""Text Embeddings Inference (TEI) client compatible with LangChain Embeddings."""

from __future__ import annotations

import httpx
from langchain_core.embeddings import Embeddings


class TeiEmbeddings(Embeddings):
    """Call a self-hosted TEI service for vectorization."""

    def __init__(self, base_url: str, timeout: float = 60.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _post_embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/embed",
                json={"inputs": texts},
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                msg = f"Unexpected TEI response type: {type(data)}"
                raise ValueError(msg)
            return data

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        return asyncio.run(self.aembed_documents(texts))

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        cleaned = [text.replace("\n", " ") for text in texts]
        return await self._post_embed(cleaned)

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    async def aembed_query(self, text: str) -> list[float]:
        return (await self.aembed_documents([text]))[0]
