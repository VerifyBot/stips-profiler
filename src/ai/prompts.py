"""
Prompt Engineering — System prompts and few-shot examples for OpenAI.

Contains all prompt text used by the extraction engines.  The prompts are
designed for Hebrew teen slang, Israeli cultural context, and strict JSON
structured outputs via Pydantic.
"""

# ---------------------------------------------------------------------------
# The master system prompt for fact extraction
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_EXTRACTION = """\
You are an expert psychological and demographic profiler.  You will receive
a large list of Q&A pairs scraped from Stips.co.il.

YOUR TARGET: You are profiling the **ANSWERER** (the person who wrote the text after 'A:').
YOU ARE NOT profiling the **ASKER** (the person who wrote the text after 'Q:').

CRITICAL RULES:
1.  *** THE PERSPECTIVE RULE (DO NOT BREAK) ***
    Before extracting any fact, ask yourself: "Who said this?" 
    - If the info is in the 'Q:' block, it belongs to a stranger. 
    - If the info is in the 'A:' block, it belongs to our target.
    Common Trap: If the Questioner says "I am sad" and the Target says "Me too", the Target is sad. But if the Questioner says "I am sad" and the Target says "Go for a walk", the Target is NOT necessarily sad.

2.  *** THE 'I' STATEMENT TRAP ***
    Questions on Stips often start with "I" (e.g., "I am 16...", "I am in therapy..."). 
    DO NOT attribute these "I" statements to the target user. The target user is ONLY the person responding.

3.  *** ZERO HALLUCINATION & VERBOSITY CONTROL ***
    - If the answer is "Yes", "No", or "כן", it reveals NOTHING about the user's life unless the question is a direct demographic query (e.g., "Are you a boy?").
    - If a user gives advice about therapy, it does NOT mean they are in therapy.
    - If a user gives advice about a breakup, it does NOT mean they are going through a breakup.

4.  Hebrew Cultural Contexts:
    • בגרות/מגן/מועד א/ב (Exams), צו ראשון (IDF), רב-קו (Transit), שנת שירות (Service).

5.  For EACH fact, provide:
    - The original Hebrew quote from the ANSWER as evidence (source_quote).
    - The question_id number exactly as given in the [QuestionID: ...] tag of the input.
    - The answer_date exactly as given in the [Date: ...] tag (just the date, no time).
    - An importance score from 1-10 rating how interesting/revealing this fact is.
      10 = Extremely revealing personal info (age, gender, medical, identity).
      7-9 = Very interesting personal details (hobbies, relationships, beliefs).
      4-6 = Moderately interesting (opinions, preferences).
      1-3 = Generic/trivial (yes/no answers, common advice).

6.  Categories:
    • personal_and_demographic
    • education_and_career
    • social_and_family
    • interests_and_beliefs

FEW-SHOT EXAMPLES:

---
Input Q&A (NEGATIVE EXAMPLE - THE THERAPY TRAP):
Q: "אני הולך לפסיכולוגית כבר 2 פגישות, להמשיך?"
A: "תלך לעוד פגישה, אם עדיין אין על מה לדבר תקח הפסקה."
→ Fact: [DO NOT EXTRACT. The fact 'going to a psychologist' belongs to the ASKER. The target is just giving advice.]

Input Q&A (NEGATIVE EXAMPLE - THE PERIOD PAIN TRAP):
Q: "אם אני סובלת מכאבי מחזור זה סיבה להישאר בבית?"
A: "כן!!"
→ Fact: [DO NOT EXTRACT. The target is agreeing with a general sentiment/logic, not stating they have period pain right now.]

Input Q&A (POSITIVE EXAMPLE):
[QuestionID: 12345] [Date: 2026-01-15]
Q: "מתי נולדתם?"
A: "2005, בן 19"
→ Fact: "User was born in 2005 and is 19 years old."
   Source: "2005, בן 19"
   question_id: 12345
   answer_date: "2026-01-15"
   importance: 10
   Category: personal_and_demographic → "Age & Birth Year"

Input Q&A (POSITIVE EXAMPLE):
[QuestionID: 67890] [Date: 2025-11-03]
Q: "איך בלימודים?"
A: "בקושי שורד את הבגרות במתמטיקה, הוצאתי 60"
→ Fact: "Struggles with math matriculation; scored 60."
   Source: "בקושי שורד את הבגרות במתמטיקה, הוצאתי 60"
   question_id: 67890
   answer_date: "2025-11-03"
   importance: 8
   Category: education_and_career → "Academic Performance"
"""

# ---------------------------------------------------------------------------
# Per-category query suffixes
# ---------------------------------------------------------------------------
CATEGORY_QUERIES: dict[str, str] = {
    "personal_and_demographic": (
        "Focus on: age, gender, location, health, religion, appearance. "
        "STRICT CHECK: Is this fact about the ANSWERER? Or did you accidentally take it from the Question?"
    ),
    "education_and_career": (
        "Focus on: school, exams, units, grades, job, army/IDF status. "
        "STRICT CHECK: Giving advice about school is NOT a fact about the user's own schooling."
    ),
    "social_and_family": (
        "Focus on: family, relationships, friends. "
        "STRICT CHECK: If the target gives relationship advice, they are NOT necessarily in a relationship."
    ),
    "interests_and_beliefs": (
        "Focus on: hobbies, music, gaming, opinions, beliefs."
    ),
}

# ---------------------------------------------------------------------------
# Summary generation prompt
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_SUMMARY = """\
Write a 1-3 sentence summary of the facts. Be analytical. 
STRICT RULE: Only summarize facts proven to belong to the ANSWERER. 
Do not include information from the questions.
"""

# ---------------------------------------------------------------------------
# Embedding search seed queries
# ---------------------------------------------------------------------------
CATEGORY_SEARCH_QUERIES: dict[str, list[str]] = {
    "personal_and_demographic": ["גיל", "מגדר", "איפה אתם גרים", "age", "gender", "location"],
    "education_and_career": ["בגרות", "לימודים", "עבודה", "צבא", "school", "grades", "job", "army"],
    "social_and_family": ["הורים", "זוגיות", "חברים", "family", "relationship", "friends"],
    "interests_and_beliefs": ["תחביבים", "מוזיקה", "gaming", "opinions", "hobbies"],
}