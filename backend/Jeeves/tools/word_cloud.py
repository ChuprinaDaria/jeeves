import re
from collections import Counter
from django.core.cache import cache

STOP_WORDS = {
    'en': {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
           'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
           'should', 'may', 'might', 'shall', 'can', 'need', 'dare', 'ought',
           'used', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
           'as', 'into', 'through', 'during', 'before', 'after', 'above', 'below',
           'between', 'out', 'off', 'over', 'under', 'again', 'further', 'then',
           'once', 'here', 'there', 'when', 'where', 'why', 'how', 'all', 'each',
           'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such', 'no',
           'nor', 'not', 'only', 'own', 'same', 'so', 'than', 'too', 'very',
           'just', 'because', 'but', 'and', 'or', 'if', 'while', 'this', 'that',
           'these', 'those', 'it', 'its', 'i', 'me', 'my', 'we', 'our', 'you',
           'your', 'he', 'him', 'his', 'she', 'her', 'they', 'them', 'their',
           'what', 'which', 'who', 'whom'},
    'de': {'der', 'die', 'das', 'ein', 'eine', 'und', 'ist', 'in', 'von', 'zu',
           'den', 'mit', 'auf', 'für', 'an', 'als', 'auch', 'es', 'ich', 'nicht',
           'sich', 'dem', 'dass', 'er', 'sie', 'wir', 'sind', 'hat', 'aus',
           'bei', 'wird', 'nach', 'wie', 'aber', 'noch', 'da', 'nur', 'wenn',
           'sein', 'ihre', 'oder', 'war', 'über', 'so', 'zum', 'im', 'haben',
           'einer', 'mir', 'um', 'des', 'bis', 'vor', 'zur', 'worden'},
    'uk': {'i', 'в', 'на', 'з', 'що', 'не', 'до', 'та', 'як', 'за', 'у',
           'це', 'але', 'для', 'вiд', 'по', 'про', 'яка', 'який', 'яке',
           'бути', 'було', 'були', 'його', 'їх', 'так', 'цей', 'ця', 'тi'},
    'pl': {'i', 'w', 'na', 'z', 'do', 'nie', 'co', 'to', 'jak', 'ale',
           'za', 'od', 'po', 'ze', 'si', 'jest', 'czy', 'tak', 'go', 'ich',
           'te', 'ten', 'ta', 'przez', 'przy', 'dla'},
    'fr': {'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'en',
           'est', 'que', 'qui', 'dans', 'pour', 'pas', 'au', 'sur', 'ce',
           'il', 'ne', 'se', 'par', 'avec', 'sont', 'son', 'sa', 'ses'},
    'it': {'il', 'lo', 'la', 'le', 'di', 'del', 'dei', 'un', 'una', 'e',
           'in', 'che', 'per', 'non', 'con', 'da', 'su', 'al', 'sono'},
}

ALL_STOP_WORDS = set()
for words in STOP_WORDS.values():
    ALL_STOP_WORDS |= words

CACHE_KEY_PREFIX = 'word_cloud'
CACHE_TTL = 3600

WORD_RE = re.compile(r'[a-zA-Zа-яА-ЯіІїЇєЄґҐąćęłńóśźżÄÖÜäöüß]+', re.UNICODE)
MIN_WORD_LEN = 3
MAX_WORDS = 80


def compute_word_frequencies(client_id):
    cache_key = f'{CACHE_KEY_PREFIX}:{client_id}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from Jeeves.clients.models import ClientEmbedding
    contents = ClientEmbedding.objects.filter(
        client_id=client_id
    ).values_list('content', flat=True)

    counter = Counter()
    for text in contents.iterator(chunk_size=500):
        words = WORD_RE.findall(text.lower())
        counter.update(
            w for w in words
            if len(w) >= MIN_WORD_LEN and w not in ALL_STOP_WORDS
        )

    result = [
        {'text': word, 'value': count}
        for word, count in counter.most_common(MAX_WORDS)
    ]

    cache.set(cache_key, result, CACHE_TTL)
    return result
