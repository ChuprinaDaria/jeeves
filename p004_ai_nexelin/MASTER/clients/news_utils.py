"""
Utility functions for automatic news generation
"""
import requests
from django.utils import timezone
from MASTER.clients.models import News


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
    image_keyword='technology'
):
    """
    Create a news item automatically.
    
    Args:
        title: News title
        description: News description
        news_type: Type of news (integration, model, feature, update, announcement)
        related_integration: Related integration name (if applicable)
        related_model: Related model name (if applicable)
        related_feature: Related feature name (if applicable)
        image_keyword: Keyword for Unsplash image search
    """
    image_url = get_unsplash_image_url(image_keyword)
    
    news = News.objects.create(
        title=title,
        description=description,
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

