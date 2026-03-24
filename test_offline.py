import asyncio
import tempfile
import unittest
from pathlib import Path

import numpy as np

# Import our modules
from src.scraper.parsers import parse_user_meta, parse_answers
from src.cache.storage import CacheStorage
from src.ai.embeddings import cosine_similarity, semantic_search
from src.ai.engines import ExtractedFact, DynamicCategory, UserProfileTree

class TestScraperParsers(unittest.TestCase):
    def test_parse_user_meta(self):
        """Test that raw API data is correctly turned into a user dict."""
        raw_api_response = {
            "status": "ok",
            "data": {
                "nickname": "test_user123",
                "flowers": 412,
                "age": 19,
                "user_profile_page": {"data": {"text_status": "Hello World"}}
            }
        }
        parsed = parse_user_meta(raw_api_response)
        self.assertEqual(parsed["nickname"], "test_user123")
        self.assertEqual(parsed["flower_count"], 412)
        self.assertEqual(parsed["age"], 19)
        self.assertEqual(parsed["text_status"], "Hello World")

    def test_parse_answers(self):
        """Test that messy answer lists are cleaned up."""
        raw_items = [
            {
                "data": {"id": 1001, "a": "My answer here", "time": "12:00"},
                "extra": {"parent_item_title": "The Question?"}
            },
            {"malformed": "data"} # Should be gracefully ignored
        ]
        parsed = parse_answers(raw_items)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["answer_id"], 1001)
        self.assertEqual(parsed[0]["question"], "The Question?")
        self.assertEqual(parsed[0]["answer"], "My answer here")


class TestCacheStorage(unittest.TestCase):
    def setUp(self):
        """Create a temporary SQLite database for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_cache.db"
        self.cache = CacheStorage(db_path=self.db_path)

    def tearDown(self):
        """Close DB and clean up the temp file."""
        self.cache.close()
        self.temp_dir.cleanup()

    def test_user_caching(self):
        """Test inserting and retrieving user metadata."""
        self.cache.save_user_meta(123, "nickname_test", 50, {"raw": "data"})
        meta = self.cache.get_user_meta(123)
        self.assertIsNotNone(meta)
        self.assertEqual(meta["nickname"], "nickname_test")
        self.assertEqual(meta["flower_count"], 50)

    def test_responses_caching(self):
        """Test bulk inserting responses and checking counts."""
        # Must insert the user first because of the FOREIGN KEY constraint
        self.cache.save_user_meta(123, "test_user", 10, {})
        
        # Insert two dummy responses
        responses = [
            {"answer_id": 1, "question": "Q1", "answer": "A1", "time": "now", "raw": {}},
            {"answer_id": 2, "question": "Q2", "answer": "A2", "time": "now", "raw": {}},
        ]
        inserted = self.cache.save_responses(user_id=123, responses=responses)
        self.assertEqual(inserted, 2)

        # Check counts and retrievals
        count = self.cache.get_response_count(123)
        self.assertEqual(count, 2)
        
        saved = self.cache.get_responses(123)
        self.assertEqual(len(saved), 2)
        
        # Test duplicate ignore logic (inserting same IDs should return 0 inserted)
        inserted_again = self.cache.save_responses(user_id=123, responses=responses)
        self.assertEqual(inserted_again, 0)


class TestEmbeddingsMath(unittest.TestCase):
    def test_cosine_similarity_and_search(self):
        """Test the pure numpy math to ensure it finds the closest vectors."""
        # Create some predictable dummy vectors
        query = np.array([1.0, 0.0, 0.0]) # Points perfectly to X axis
        
        corpus = np.array([
            [0.0, 1.0, 0.0], # Completely orthogonal (similarity 0)
            [0.9, 0.1, 0.0], # Very close to query
            [-1.0, 0.0, 0.0] # Opposite direction (similarity -1)
        ])

        # semantic_search should return index 1 as the best match
        best_indices = semantic_search(query, corpus, top_k=1)
        self.assertEqual(best_indices[0], 1)


class TestPydanticSchema(unittest.TestCase):
    def test_tree_generation(self):
        """Test that the Pydantic models can serialize to the UI dict format."""
        fact = ExtractedFact(fact="Loves Python", source_quote="פייתון זה מעולה")
        category = DynamicCategory(category_name="Programming", facts=[fact])
        
        tree = UserProfileTree(
            personal_and_demographic=[],
            education_and_career=[category],
            social_and_family=[],
            interests_and_beliefs=[]
        )
        
        # Ensure the total facts counter works
        self.assertEqual(tree.total_facts(), 1)
        
        # Ensure it formats perfectly for the Textual Dashboard
        display_dict = tree.to_display_dict()
        self.assertIn("🎓 Education & Career", display_dict)
        self.assertIn("Programming (1 facts)", display_dict["🎓 Education & Career"])


if __name__ == "__main__":
    unittest.main()