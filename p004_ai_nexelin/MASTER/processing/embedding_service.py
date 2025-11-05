from django.conf import settings
# pyright: reportMissingTypeStubs=false
from MASTER.EmbeddingModel.models import EmbeddingModel


class EmbeddingService:
    @staticmethod
    def embed_text(text: str, model_name: str):
        """Створює embedding для одиничного тексту через OpenAI з обробкою помилок і локальним fallback.

        Повертає dict: { 'vector': list[float], 'token_count': int, 'dimensions': int }
        """
        try:
            return EmbeddingService._openai_embed(text, model_name)
        except Exception:  # noqa: BLE001
            if getattr(settings, "EMBEDDINGS_FALLBACK_LOCAL", True):
                return EmbeddingService._local_tfidf_embed(text)
            raise

    @staticmethod
    def embed_batch(texts: list[str], model_name: str):
        """Створює embeddings для списку текстів батчем. При помилці — локальний TF-IDF fallback.

        Повертає list[dict], де кожен елемент: { 'vector': list[float], 'token_count': int, 'dimensions': int }
        """
        try:
            from openai import OpenAI
            import tiktoken  # type: ignore[reportMissingImports]

            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            encoding = tiktoken.encoding_for_model(model_name)
            token_counts = [len(encoding.encode(t)) for t in texts]

            response = client.embeddings.create(input=texts, model=model_name)
            vectors = [d.embedding for d in response.data]

            results = []
            for vec, tok in zip(vectors, token_counts):
                results.append({
                    'vector': vec,
                    'token_count': tok,
                    'dimensions': len(vec),
                })
            return results
        except Exception:  # noqa: BLE001
            if getattr(settings, "EMBEDDINGS_FALLBACK_LOCAL", True):
                return EmbeddingService._local_tfidf_embed_batch(texts)
            raise
    @staticmethod
    def create_embedding(text, embedding_model: EmbeddingModel):
        provider = embedding_model.provider
        model_name = embedding_model.model_name
        
        try:
            if provider == 'openai':
                result = EmbeddingService._openai_embed(text, model_name)
            elif provider == 'huggingface':
                result = EmbeddingService._huggingface_embed(text, model_name)
            elif provider == 'cohere':
                result = EmbeddingService._cohere_embed(text, model_name)
            else:
                raise ValueError(f"Unknown provider: {provider}")

            # Normalize vector dimensions to match configured model dimensions
            try:
                target_dim = int(embedding_model.dimensions)
                vec = result.get('vector')
                if isinstance(vec, list):
                    current_dim = len(vec)
                    if current_dim != target_dim:
                        # Truncate or pad with zeros to exactly target_dim
                        if current_dim > target_dim:
                            vec = vec[:target_dim]
                        else:
                            vec = vec + [0.0] * (target_dim - current_dim)
                        result['vector'] = vec
                        result['dimensions'] = target_dim
            except Exception:
                # In case of any unexpected issue, return original result
                pass

            return result
        except Exception:  # noqa: BLE001
            if getattr(settings, "EMBEDDINGS_FALLBACK_LOCAL", True):
                return EmbeddingService._local_tfidf_embed(text)
            raise
    
    @staticmethod
    def _openai_embed(text: str, model_name: str):
        from openai import OpenAI
        import tiktoken  # type: ignore[reportMissingImports]
        
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        encoding = tiktoken.encoding_for_model(model_name)
        tokens = encoding.encode(text)
        token_count = len(tokens)
        
        response = client.embeddings.create(
            input=text,
            model=model_name
        )
        
        vector = response.data[0].embedding
        
        return {
            'vector': vector,
            'token_count': token_count,
            'dimensions': len(vector)
        }

    @staticmethod
    def _local_tfidf_embed(text: str):
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[reportMissingTypeStubs]
        import numpy as np

        vectorizer = TfidfVectorizer(
            max_features=1536,
            ngram_range=(1, 2),
        )
        X = vectorizer.fit_transform([text])
        try:
            vec_arr: np.ndarray = X.toarray()[0]  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            vec_arr = np.asarray(X)[0]
        
        # Доповнюємо або обрізаємо вектор до 1536 розмірностей
        target_dim = 1536
        if len(vec_arr) < target_dim:
            # Доповнюємо нулями
            vec_arr = np.pad(vec_arr, (0, target_dim - len(vec_arr)), 'constant')
        elif len(vec_arr) > target_dim:
            # Обрізаємо
            vec_arr = vec_arr[:target_dim]
        
        vector = [float(v) for v in vec_arr]

        token_count = len(text.split())
        return {
            'vector': vector,
            'token_count': token_count,
            'dimensions': len(vector)
        }
    
    @staticmethod
    def _local_tfidf_embed_batch(texts: list[str]):
        # Батчевий локальний резервний варіант — спільний словник ознак для всіх елементів батчу
        from sklearn.feature_extraction.text import TfidfVectorizer  # type: ignore[reportMissingTypeStubs]
        import numpy as np

        vectorizer = TfidfVectorizer(
            max_features=1536,
            ngram_range=(1, 2),
        )
        X = vectorizer.fit_transform(texts)
        try:
            arr: np.ndarray = X.toarray()  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            arr = np.asarray(X)
        
        # Доповнюємо або обрізаємо вектори до 1536 розмірностей
        target_dim = 1536
        if arr.shape[1] < target_dim:
            # Доповнюємо нулями
            padding = np.zeros((arr.shape[0], target_dim - arr.shape[1]))
            arr = np.hstack([arr, padding])
        elif arr.shape[1] > target_dim:
            # Обрізаємо
            arr = arr[:, :target_dim]
        
        results = []
        for i, row in enumerate(arr):
            vector = [float(v) for v in row]
            token_count = len(texts[i].split())
            results.append({
                'vector': vector,
                'token_count': token_count,
                'dimensions': len(vector),
            })
        return results
    
    @staticmethod
    def _huggingface_embed(text: str, model_name: str):
        raise NotImplementedError("HuggingFace embedding not implemented yet")
    
    @staticmethod
    def _cohere_embed(text: str, model_name: str):
        raise NotImplementedError("Cohere embedding not implemented yet")
    
    @staticmethod
    def calculate_cost(token_count: int, embedding_model: EmbeddingModel) -> float:
        cost_per_1k = float(embedding_model.cost_per_1k_tokens)
        return (token_count / 1000.0) * cost_per_1k


