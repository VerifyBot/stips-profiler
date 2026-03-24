md = """# Future AI Roadmap & Advanced Scaling

As the tool matures and handles massive Stips power users, we will implement these advanced techniques to fully automate discovery and reduce API costs.

## 1. AI Topic Clustering (The "Unknown Unknowns" Finder)
**Problem:** For users with 2,000+ answers, Embeddings (Strategy 2) requires us to guess the search targets. If we don't know they like "K-Pop", we won't search for it.
**Solution:**
1. Turn all answers into vector embeddings.
2. Use a math library (`scikit-learn` using K-Means or HDBSCAN) to automatically group the vectors into clusters based on semantic similarity.
3. Take the top 5 answers from a cluster and pass them to a cheap LLM.
4. Ask: *"What are these answers talking about? Give it a 2-word category name."*
5. The system dynamically generates completely novel "Trunks" and "Branches" without any human guessing.

## 2. Model Fine-Tuning
**Problem:** OPENAI for heavy extraction gets expensive at scale.
**Solution:**
1. Curate a dataset of 300-500 perfectly extracted Stips user profiles (Input: Raw Q&A -> Output: Perfect JSON tree).
2. Fine-tune a smaller, cheaper model (like Llama 3 8B or GPT-4o-mini).
3. The fine-tuned model will inherently understand the slang, the JSON schema, and the exact tone required, removing the need for massive Few-Shot prompts and significantly cutting API costs.
"""