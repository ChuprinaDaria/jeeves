from django.db import migrations

MESSAGES = [
    ('chat.timeout', 'Shown when chat session times out', {
        'en': 'Session timed out. Please start a new conversation.',
        'de': 'Sitzung abgelaufen. Bitte starten Sie eine neue Konversation.',
        'fr': 'Session expirée. Veuillez démarrer une nouvelle conversation.',
        'es': 'Sesión expirada. Por favor, inicie una nueva conversación.',
        'it': 'Sessione scaduta. Si prega di iniziare una nuova conversazione.',
        'nl': 'Sessie verlopen. Start een nieuw gesprek.',
        'da': 'Session udløbet. Start venligst en ny samtale.',
    }),
    ('chat.waiting', 'Shown while AI is processing', {
        'en': 'Please wait...',
        'de': 'Bitte warten...',
        'fr': 'Veuillez patienter...',
        'es': 'Por favor, espere...',
        'it': 'Attendere prego...',
        'nl': 'Even geduld...',
        'da': 'Vent venligst...',
    }),
    ('chat.escalation', 'Shown when escalating to manager', {
        'en': 'Connecting you to a manager...',
        'de': 'Verbinde Sie mit einem Manager...',
        'fr': 'Connexion avec un responsable...',
        'es': 'Conectando con un gerente...',
        'it': 'Collegamento con un responsabile...',
        'nl': 'Verbinden met een manager...',
        'da': 'Forbinder dig med en leder...',
    }),
    ('chat.greeting_default', 'Default greeting when none configured', {
        'en': 'Hello! How can I help you?',
        'de': 'Hallo! Wie kann ich Ihnen helfen?',
        'fr': 'Bonjour! Comment puis-je vous aider?',
        'es': '¡Hola! ¿Cómo puedo ayudarle?',
        'it': 'Ciao! Come posso aiutarti?',
        'nl': 'Hallo! Hoe kan ik u helpen?',
        'da': 'Hej! Hvordan kan jeg hjælpe dig?',
    }),
    ('chat.no_answer', 'When AI cannot find relevant information', {
        'en': "I don't have enough information to answer this question.",
        'de': 'Ich habe nicht genug Informationen, um diese Frage zu beantworten.',
        'fr': "Je n'ai pas assez d'informations pour répondre à cette question.",
        'es': 'No tengo suficiente información para responder a esta pregunta.',
        'it': 'Non ho abbastanza informazioni per rispondere a questa domanda.',
        'nl': 'Ik heb niet genoeg informatie om deze vraag te beantwoorden.',
        'da': 'Jeg har ikke nok information til at besvare dette spørgsmål.',
    }),
]


def forward(apps, schema_editor):
    SystemMessage = apps.get_model('concierge_platform', 'SystemMessage')
    for key, desc, translations in MESSAGES:
        SystemMessage.objects.get_or_create(
            key=key, defaults={'description': desc, 'translations': translations})


def reverse(apps, schema_editor):
    SystemMessage = apps.get_model('concierge_platform', 'SystemMessage')
    keys = [m[0] for m in MESSAGES]
    SystemMessage.objects.filter(key__in=keys).delete()


class Migration(migrations.Migration):
    dependencies = [('concierge_platform', '0002_seed_platform_defaults')]
    operations = [migrations.RunPython(forward, reverse)]
