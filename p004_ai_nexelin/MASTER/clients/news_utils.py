"""
Utility functions for automatic news generation
"""
import requests
import logging
from django.utils import timezone
from django.conf import settings
from MASTER.clients.models import News

logger = logging.getLogger(__name__)

# Supported languages in the app (matching frontend locales: en, de, fr, es, it, nl, da)
SUPPORTED_LANGUAGES = ['en', 'de', 'es', 'fr', 'it', 'nl', 'da']

# Language names for translation prompts
LANGUAGE_NAMES = {
    'en': 'English',
    'de': 'German',
    'es': 'Spanish',
    'fr': 'French',
    'it': 'Italian',
    'nl': 'Dutch',
    'da': 'Danish',
}


def get_unsplash_image_url(keyword='technology', width=800, height=600):
    """
    Get a random image URL from Unsplash based on keyword.
    Falls back to a placeholder if Unsplash API is not available.
    """
    try:
        # Використовуємо Unsplash Source API (без API ключа)
        url = f"https://source.unsplash.com/{width}x{height}/?{keyword}"
        return url
    except Exception:
        # Fallback to placeholder
        return f"https://via.placeholder.com/{width}x{height}?text=News"


def create_news(
    title,
    description,
    news_type='update',
    related_integration='',
    related_model='',
    related_feature='',
    image_keyword='technology',
    auto_translate=True
):
    """
    Create a news item automatically.
    
    Args:
        title: News title (in English)
        description: News description (in English)
        news_type: Type of news (integration, model, feature, update, announcement)
        related_integration: Related integration name (if applicable)
        related_model: Related model name (if applicable)
        related_feature: Related feature name (if applicable)
        image_keyword: Keyword for Unsplash image search
        auto_translate: Whether to automatically generate translations
    """
    image_url = get_unsplash_image_url(image_keyword)
    
    # Generate translations if enabled
    translations = {}
    if auto_translate:
        try:
            translations = generate_translations(title, description)
        except Exception as e:
            logger.error(f"Failed to generate translations: {e}", exc_info=True)
            # Continue without translations
    
    news = News.objects.create(
        title=title,
        description=description,
        translations=translations,
        news_type=news_type,
        image_url=image_url,
        related_integration=related_integration,
        related_model=related_model,
        related_feature=related_feature,
        is_active=True,
        is_featured=(news_type in ['feature', 'announcement'])
    )
    
    return news


def create_integration_news(integration_name, description=None):
    """Create news for new integration"""
    if not description:
        description = f"New {integration_name} integration is now available! Connect your AI assistant to {integration_name} and enhance your customer communication."
    
    keywords_map = {
        'telegram': 'telegram',
        'whatsapp': 'whatsapp',
        'web widget': 'website',
        'calendar': 'calendar',
    }
    
    keyword = keywords_map.get(integration_name.lower(), 'technology')
    
    return create_news(
        title=f"New Integration: {integration_name}",
        description=description,
        news_type='integration',
        related_integration=integration_name,
        image_keyword=keyword
    )


def create_model_news(model_name, description=None):
    """Create news for new model"""
    if not description:
        description = f"New AI model {model_name} is now available! Experience improved performance and accuracy with the latest model."
    
    return create_news(
        title=f"New Model Available: {model_name}",
        description=description,
        news_type='model',
        related_model=model_name,
        image_keyword='artificial intelligence'
    )


def create_feature_news(feature_name, description=None):
    """Create news for new feature"""
    if not description:
        description = f"New feature {feature_name} is now available! Enhance your AI assistant with this powerful new capability."
    
    return create_news(
        title=f"New Feature: {feature_name}",
        description=description,
        news_type='feature',
        related_feature=feature_name,
        image_keyword='innovation'
    )


def translate_text(text: str, target_language: str) -> str:
    """
    Translate text to target language using OpenAI API.
    
    Args:
        text: Text to translate
        target_language: Target language code (en, de, es, fr, it, nl, da)
    
    Returns:
        Translated text or original text if translation fails
    """
    if target_language == 'en':
        return text  # English is the default
    
    if target_language not in SUPPORTED_LANGUAGES:
        logger.warning(f"Unsupported language: {target_language}")
        return text
    
    try:
        from openai import OpenAI
        
        # Try to get OpenAI API key from settings
        api_key = getattr(settings, 'OPENAI_API_KEY', None)
        if not api_key:
            logger.warning("OPENAI_API_KEY not configured, skipping translation")
            return text
        
        client = OpenAI(api_key=api_key)
        language_name = LANGUAGE_NAMES.get(target_language, target_language)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use cheap model for translations
            messages=[
                {
                    "role": "system",
                    "content": f"You are a professional translator. Translate the following text to {language_name}. Return only the translation, no explanations."
                },
                {
                    "role": "user",
                    "content": text
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        translated = response.choices[0].message.content.strip()
        logger.info(f"Translated text to {target_language}: {text[:50]}... -> {translated[:50]}...")
        return translated
        
    except Exception as e:
        logger.error(f"Translation failed for {target_language}: {e}", exc_info=True)
        return text  # Return original text on failure


def generate_translations(title: str, description: str) -> dict:
    """
    Generate translations for title and description in all supported languages.
    
    Args:
        title: English title
        description: English description
    
    Returns:
        Dictionary with translations: {"en": {"title": "...", "description": "..."}, "de": {...}, ...}
    """
    translations = {}
    
    for lang_code in SUPPORTED_LANGUAGES:
        if lang_code == 'en':
            # English is the default
            translations[lang_code] = {
                'title': title,
                'description': description
            }
        else:
            # Translate to other languages
            try:
                translated_title = translate_text(title, lang_code)
                translated_description = translate_text(description, lang_code)
                
                translations[lang_code] = {
                    'title': translated_title,
                    'description': translated_description
                }
            except Exception as e:
                logger.error(f"Failed to generate translation for {lang_code}: {e}")
                # Fallback to English
                translations[lang_code] = {
                    'title': title,
                    'description': description
                }
    
    return translations

