"""Owner ↔ Jeeves Telegram link: code endpoint + webhook routing."""
import json
from unittest.mock import patch

import pytest
from django.core.cache import cache

from Jeeves.clients.models import Client


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client_obj(db):
    return Client.objects.create(
        user='test', description='test', api_key='rag_test_key_tg',
        tag='tg-client', telegram_bot_token='123:abc')


def _tg_message(chat_id, text):
    return {
        'message': {
            'chat': {'id': chat_id},
            'from': {'id': chat_id, 'username': 'owner', 'first_name': 'O'},
            'text': text,
        }
    }


@pytest.mark.django_db
class TestOwnerTelegramLinkEndpoint:
    URL = '/api/clients/owner-telegram/'

    def test_status_and_code_generation(self, client, client_obj):
        res = client.get(self.URL, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        assert res.json() == {'linked': False, 'bot_configured': True}

        res = client.post(self.URL, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        body = res.json()
        assert body['command'] == f"/jeeves {body['code']}"
        assert cache.get(f"tg-owner-code:{body['code']}") == client_obj.pk

    def test_requires_bot_configured(self, client, client_obj):
        client_obj.telegram_bot_token = ''
        client_obj.save()
        res = client.post(self.URL, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        assert res.status_code == 400

    def test_unlink(self, client, client_obj):
        client_obj.owner_telegram_chat_id = '777'
        client_obj.save()
        res = client.delete(self.URL, HTTP_X_CLIENT_TOKEN=client_obj.tag)
        assert res.json() == {'linked': False}
        client_obj.refresh_from_db()
        assert client_obj.owner_telegram_chat_id == ''


@pytest.mark.django_db
class TestOwnerTelegramWebhook:
    URL = '/api/clients/telegram/webhook/'

    @patch('Jeeves.clients.views_telegram.send_telegram_message')
    def test_jeeves_link_with_valid_code(self, mock_send, client, client_obj):
        cache.set('tg-owner-code:ABC123', client_obj.pk, 600)
        res = client.post(self.URL, json.dumps(_tg_message(777, '/jeeves ABC123')),
                          content_type='application/json')
        assert res.status_code == 200
        client_obj.refresh_from_db()
        assert client_obj.owner_telegram_chat_id == '777'
        assert cache.get('tg-owner-code:ABC123') is None
        assert mock_send.called

    @patch('Jeeves.clients.views_telegram.send_telegram_message')
    def test_jeeves_link_invalid_code(self, mock_send, client, client_obj):
        res = client.post(self.URL, json.dumps(_tg_message(777, '/jeeves WRONG1')),
                          content_type='application/json')
        assert res.status_code == 200
        client_obj.refresh_from_db()
        assert client_obj.owner_telegram_chat_id == ''

    @patch('Jeeves.clients.views_telegram.send_telegram_message')
    @patch('Jeeves.agents.dispatch.generate_response_dual', return_value='pong')
    def test_owner_chat_routes_to_jeeves(self, mock_gen, mock_send, client, client_obj):
        client_obj.owner_telegram_chat_id = '777'
        client_obj.save()
        res = client.post(self.URL, json.dumps(_tg_message(777, 'покажи звіт за тиждень')),
                          content_type='application/json',
                          HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=client_obj.tag)
        assert res.status_code == 200
        assert mock_gen.called
        kwargs = mock_gen.call_args.kwargs
        assert kwargs['channel'] == 'owner_telegram'
        assert kwargs['client'].pk == client_obj.pk
        # reply went back to the owner chat
        assert mock_send.call_args.args[1] == 777
        assert mock_send.call_args.args[2] == 'pong'

    @patch('Jeeves.clients.views_telegram.send_telegram_message')
    @patch('Jeeves.agents.dispatch.generate_response_dual', return_value='pong')
    def test_other_tenant_cannot_reach_owner_jeeves(self, mock_gen, mock_send, client, client_obj):
        # Client B links chat 777 to ITS owner assistant.
        Client.objects.create(
            user='b', description='d', api_key='rag_test_key_tg2',
            tag='tg-client-b', telegram_bot_token='999:xyz',
            owner_telegram_chat_id='777')
        # A message arrives on Client A's bot (resolved via A's secret_token),
        # from a chat that happens to equal B's linked owner chat_id.
        client.post(
            self.URL, json.dumps(_tg_message(777, 'leak my data')),
            content_type='application/json',
            HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=client_obj.tag)
        # B's private Jeeves (assistant scope) must NOT be invoked for A's bot
        # traffic — no call may use the owner_telegram channel.
        owner_calls = [c for c in mock_gen.call_args_list
                       if c.kwargs.get('channel') == 'owner_telegram']
        assert owner_calls == []

    @patch('Jeeves.clients.views_telegram.send_telegram_message')
    @patch('Jeeves.agents.dispatch.generate_response_dual', return_value='pong')
    def test_owner_unlink_command(self, mock_gen, mock_send, client, client_obj):
        client_obj.owner_telegram_chat_id = '777'
        client_obj.save()
        client.post(self.URL, json.dumps(_tg_message(777, '/unlink')),
                    content_type='application/json',
                    HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN=client_obj.tag)
        client_obj.refresh_from_db()
        assert client_obj.owner_telegram_chat_id == ''
        assert not mock_gen.called
