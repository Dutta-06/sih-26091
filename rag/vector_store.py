from __future__ import annotations

import os
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

class LocalKeywordRetriever(BaseRetriever):
    """A mock retriever that searches local text files for keywords instead of using real embeddings."""
    
    data_dir: str = Field(default_factory=lambda: str(Path(__file__).parent.parent / "data" / "scheme_guidelines"))
    
    def _get_relevant_documents(self, query: str, *, run_manager=None) -> List[Document]:
        docs = []
        if not os.path.exists(self.data_dir):
            return docs
            
        query_lower = query.lower()
        for filename in os.listdir(self.data_dir):
            if not filename.endswith(".md"):
                continue
            
            filepath = os.path.join(self.data_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Very simple mock vector retrieval logic (keyword match)
            # In a real environment, this would be a FAISS or Chroma similarity_search.
            if "micro" in query_lower and "micro" in filename.lower():
                docs.append(Document(page_content=content, metadata={"source": filename}))
            elif "term" in query_lower and "term" in filename.lower():
                docs.append(Document(page_content=content, metadata={"source": filename}))
                
        # Fallback if no exact tier matched
        if not docs:
            for filename in os.listdir(self.data_dir):
                if filename.endswith(".md"):
                    with open(os.path.join(self.data_dir, filename), "r", encoding="utf-8") as f:
                        docs.append(Document(page_content=f.read(), metadata={"source": filename}))
                        
        return docs

def get_retriever() -> BaseRetriever:
    return LocalKeywordRetriever()
