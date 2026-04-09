import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import ScheduleGrid, { DEFAULT_SCHEDULE } from './ScheduleGrid';
import ContactFilter from './ContactFilter';
import { autoReplyAPI } from '../../api/autoReply';

const TIMEZONE_REGIONS = ['Africa', 'America', 'Asia', 'Atlantic', 'Australia', 'Europe', 'Indian', 'Pacific'];

const getTimezones = () => {
  try {
    return Intl.supportedValuesOf('timeZone');
  } catch {
    return ['UTC', 'Europe/Warsaw', 'Europe/Berlin', 'America/New_York'];
  }
};

const ChannelCard = ({ channel, channelLabel, connectionInfo, initialConfig }) => {
  const { t } = useTranslation();

  const [enabled, setEnabled] = useState(initialConfig?.enabled ?? true);
  const [scheduleMode, setScheduleMode] = useState(initialConfig?.schedule_mode || 'always');
  const [timezone, setTimezone] = useState(
    initialConfig?.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  );
  const [schedule, setSchedule] = useState(initialConfig?.schedule || DEFAULT_SCHEDULE);
  const [contactMode, setContactMode] = useState(initialConfig?.contact_mode || 'all');
  const [contactList, setContactList] = useState(initialConfig?.contact_list || []);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  const allTimezones = getTimezones();
  const noDaysActive = scheduleMode === 'scheduled' && schedule.every(d => !d.enabled);

  const handleSave = async () => {
    setSaving(true);
    setMessage(null);
    try {
      await autoReplyAPI.save(channel, {
        enabled,
        schedule_mode: scheduleMode,
        timezone,
        schedule,
        contact_mode: contactMode,
        contact_list: contactList,
      });
      setMessage({ type: 'success', text: t('settings.saved') });
      setTimeout(() => setMessage(null), 3000);
    } catch (err) {
      const detail = err.response?.data?.detail || err.response?.data?.schedule?.[0] || 'Error saving';
      setMessage({ type: 'error', text: String(detail) });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100 dark:border-gray-700">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{channelLabel}</h3>
          {connectionInfo && (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t('settings.connected')}: {connectionInfo}
            </p>
          )}
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={e => setEnabled(e.target.checked)}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none rounded-full peer dark:bg-gray-600 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-500" />
        </label>
      </div>

      {enabled && (
        <div className="px-6 py-4 space-y-6">
          {/* Schedule Section */}
          <div>
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              {t('settings.scheduleTitle')}
            </h4>
            <div className="space-y-2 mb-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name={`schedule-${channel}`}
                  checked={scheduleMode === 'always'}
                  onChange={() => setScheduleMode('always')}
                  className="w-4 h-4 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {t('settings.scheduleAlways')}
                </span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name={`schedule-${channel}`}
                  checked={scheduleMode === 'scheduled'}
                  onChange={() => setScheduleMode('scheduled')}
                  className="w-4 h-4 text-primary-500 focus:ring-primary-500"
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {t('settings.scheduleScheduled')}
                </span>
              </label>
            </div>

            {scheduleMode === 'scheduled' && (
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                    {t('settings.timezone')}
                  </label>
                  <select
                    value={timezone}
                    onChange={e => setTimezone(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm"
                  >
                    {TIMEZONE_REGIONS.map(region => {
                      const tzs = allTimezones.filter(tz => tz.startsWith(region + '/'));
                      if (tzs.length === 0) return null;
                      return (
                        <optgroup key={region} label={region}>
                          {tzs.map(tz => (
                            <option key={tz} value={tz}>{tz.replace('_', ' ')}</option>
                          ))}
                        </optgroup>
                      );
                    })}
                    <option value="UTC">UTC</option>
                  </select>
                </div>
                <ScheduleGrid schedule={schedule} onChange={setSchedule} />
                {noDaysActive && (
                  <p className="text-sm text-amber-600 dark:text-amber-400">
                    {t('settings.noDaysActive')}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Contact Filter Section */}
          <div>
            <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
              {t('settings.contactFilterTitle')}
            </h4>
            <ContactFilter
              channel={channel}
              contactMode={contactMode}
              contactList={contactList}
              onModeChange={setContactMode}
              onListChange={setContactList}
            />
          </div>

          {/* Message */}
          {message && (
            <div className={`text-sm px-3 py-2 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                : 'bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
            }`}>
              {message.text}
            </div>
          )}

          {/* Save Button */}
          <div className="flex justify-end">
            <button onClick={handleSave} disabled={saving} className="btn-primary text-sm flex items-center gap-2">
              {saving && <Loader2 size={16} className="animate-spin" />}
              {t('settings.saveChanges')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default ChannelCard;
