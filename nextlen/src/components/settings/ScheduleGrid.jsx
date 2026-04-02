import { useTranslation } from 'react-i18next';

const DAYS = [
  { key: 0, i18n: 'dayMon' },
  { key: 1, i18n: 'dayTue' },
  { key: 2, i18n: 'dayWed' },
  { key: 3, i18n: 'dayThu' },
  { key: 4, i18n: 'dayFri' },
  { key: 5, i18n: 'daySat' },
  { key: 6, i18n: 'daySun' },
];

const DEFAULT_SCHEDULE = DAYS.map(d => ({
  day: d.key,
  start: d.key < 5 ? '09:00' : '10:00',
  end: d.key < 5 ? '18:00' : '14:00',
  enabled: d.key < 5,
}));

const ScheduleGrid = ({ schedule, onChange }) => {
  const { t } = useTranslation();

  const fullSchedule = DAYS.map(d => {
    const existing = (schedule || []).find(s => s.day === d.key);
    return existing || DEFAULT_SCHEDULE.find(s => s.day === d.key);
  });

  const updateDay = (dayIndex, field, value) => {
    const updated = fullSchedule.map(entry =>
      entry.day === dayIndex ? { ...entry, [field]: value } : entry
    );
    onChange(updated);
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400">
            <th className="py-2 pr-4 font-medium">Day</th>
            <th className="py-2 px-2 font-medium">{t('settings.start')}</th>
            <th className="py-2 px-2 font-medium">{t('settings.end')}</th>
            <th className="py-2 pl-2 font-medium text-center">{t('settings.enabled')}</th>
          </tr>
        </thead>
        <tbody>
          {DAYS.map(d => {
            const entry = fullSchedule.find(s => s.day === d.key);
            return (
              <tr key={d.key} className={`border-t border-gray-100 dark:border-gray-700 ${!entry.enabled ? 'opacity-50' : ''}`}>
                <td className="py-2 pr-4 font-medium text-gray-700 dark:text-gray-300">
                  {t(`settings.${d.i18n}`)}
                </td>
                <td className="py-2 px-2">
                  <input
                    type="time"
                    value={entry.start}
                    onChange={e => updateDay(d.key, 'start', e.target.value)}
                    disabled={!entry.enabled}
                    className="w-28 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm disabled:opacity-40"
                  />
                </td>
                <td className="py-2 px-2">
                  <input
                    type="time"
                    value={entry.end}
                    onChange={e => updateDay(d.key, 'end', e.target.value)}
                    disabled={!entry.enabled}
                    className="w-28 px-2 py-1 rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm disabled:opacity-40"
                  />
                </td>
                <td className="py-2 pl-2 text-center">
                  <input
                    type="checkbox"
                    checked={entry.enabled}
                    onChange={e => updateDay(d.key, 'enabled', e.target.checked)}
                    className="w-4 h-4 rounded border-gray-300 text-primary-500 focus:ring-primary-500"
                  />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};

export { DEFAULT_SCHEDULE };
export default ScheduleGrid;
