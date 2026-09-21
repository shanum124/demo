from ai_services.config import get_settings
from .vector_store import VectorStore
from .pyq_store import PYQStore
from .syllabus_store import SyllabusStore
from .mock_store import MockStore
from .markdown_store import MarkdownStore

def build_stores():
    s = get_settings()
    return (
        VectorStore(
            path=s.qdrant_dir,
            url=s.qdrant_url,
            api_key=s.qdrant_api_key,
            collection_name=s.qdrant_collection,
            embedding_model=s.embedding_model,
            vector_size=s.embedding_dimension,
            local_files_only=s.embedding_local_files_only,
        ),
        PYQStore(s.sqlite_path),
        SyllabusStore(s.sqlite_path),
        MockStore(s.sqlite_path),
        MarkdownStore(s.sqlite_path, s.data_dir),
    )
