"""
Translation Utility - Using deep-translator for quiz translation
"""
import asyncio
from typing import Optional, List, Dict
from deep_translator import GoogleTranslator

from config import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


async def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """Translate text to target language with retry logic"""
    if not text or not text.strip():
        return text
    
    if target_lang == "en" and source_lang == "en":
        return text
    
    try:
        # Run in executor to make it async
        loop = asyncio.get_event_loop()
        translator = GoogleTranslator(source=source_lang, target=target_lang)
        result = await loop.run_in_executor(
            None,
            lambda: translator.translate(text)
        )
        return result if result else text
    except Exception as e:
        # Retry once
        try:
            await asyncio.sleep(0.5)
            translator = GoogleTranslator(source=source_lang, target=target_lang)
            result = await loop.run_in_executor(
                None,
                lambda: translator.translate(text)
            )
            return result if result else text
        except Exception:
            # Return original text if translation fails
            return text


async def translate_question(question: dict, target_lang: str) -> dict:
    """Translate a single question with its options"""
    if target_lang == "en":
        return question
    
    translated = question.copy()
    
    # Translate question text
    translated['question_text'] = await translate_text(
        question['question_text'], 
        target_lang
    )
    
    # Translate options
    translated_options = []
    for option in question.get('options', []):
        translated_option = await translate_text(option, target_lang)
        translated_options.append(translated_option)
    
    translated['options'] = translated_options
    
    return translated


async def translate_questions_batch(
    questions: List[dict], 
    target_lang: str,
    cached_translations: Optional[Dict] = None
) -> List[dict]:
    """Translate a batch of questions with caching support"""
    if target_lang == "en":
        return questions
    
    translated_questions = []
    
    for question in questions:
        q_id = question.get('question_id', '')
        
        # Check cache first
        if cached_translations and q_id in cached_translations:
            cached = cached_translations[q_id]
            if target_lang in cached:
                translated_questions.append(cached[target_lang])
                continue
        
        # Translate if not cached
        translated = await translate_question(question, target_lang)
        translated_questions.append(translated)
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.1)
    
    return translated_questions


def get_language_name(lang_code: str) -> str:
    """Get language name from code"""
    return SUPPORTED_LANGUAGES.get(lang_code, lang_code)


def is_valid_language(lang_code: str) -> bool:
    """Check if language code is valid"""
    return lang_code in SUPPORTED_LANGUAGES
