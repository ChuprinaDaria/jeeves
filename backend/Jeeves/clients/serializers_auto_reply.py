import re
from rest_framework import serializers
from .models_auto_reply import ChannelAutoReply

TIME_RE = re.compile(r'^\d{2}:\d{2}$')


class ChannelAutoReplySerializer(serializers.ModelSerializer):
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)

    class Meta:
        model = ChannelAutoReply
        fields = [
            'channel', 'channel_display', 'enabled',
            'schedule_mode', 'timezone', 'schedule',
            'contact_mode', 'contact_list',
        ]
        read_only_fields = ['channel']

    def validate_schedule(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Schedule must be a list.')
        seen_days = set()
        for entry in value:
            if not isinstance(entry, dict):
                raise serializers.ValidationError('Each schedule entry must be an object.')
            day = entry.get('day')
            if day is None or not isinstance(day, int) or not (0 <= day <= 6):
                raise serializers.ValidationError(f'Invalid day: {day}. Must be 0-6.')
            if day in seen_days:
                raise serializers.ValidationError(f'Duplicate day: {day}.')
            seen_days.add(day)
            for field in ('start', 'end'):
                t = entry.get(field, '')
                if not TIME_RE.match(str(t)):
                    raise serializers.ValidationError(f'Invalid {field} time: {t}. Use HH:MM format.')
            if entry.get('start', '00:00') >= entry.get('end', '23:59'):
                raise serializers.ValidationError(
                    f'Day {day}: start must be before end (overnight not supported).'
                )
            if 'enabled' not in entry:
                raise serializers.ValidationError(f'Day {day}: "enabled" field is required.')
        return value

    def validate_contact_list(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('Contact list must be a list.')
        cleaned = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise serializers.ValidationError(f'Invalid contact: {item}')
            cleaned.append(item.lstrip('+').replace(' ', '').replace('-', ''))
        return cleaned

    def validate_timezone(self, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, KeyError):
            raise serializers.ValidationError(f'Invalid timezone: {value}')
        return value
