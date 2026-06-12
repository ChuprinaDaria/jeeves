import { X } from 'lucide-react';

const CalendarSetup = ({ onClose }) => {
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-ink/30 backdrop-blur-[2px]">
      <div className="settings-drawer bg-white dark:bg-gray-800 h-full overflow-y-auto border-l-[1.5px] border-rule shadow-ink-lg p-6 w-[480px] max-w-[94vw]">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Setup Calendar Integration</h3>
          <button onClick={onClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300">
            <X size={24} />
          </button>
        </div>

        <div className="space-y-4">
          <p className="text-gray-600 dark:text-gray-400">
            Connect your Google Calendar to enable automatic booking management.
          </p>

          <div className="bg-purple-50 dark:bg-purple-900/30 border border-purple-200 dark:border-purple-700 rounded-lg p-4">
            <p className="text-sm text-purple-800 dark:text-purple-300 mb-2">
              <strong>What will be synced:</strong>
            </p>
            <ul className="text-sm text-purple-700 dark:text-purple-300 space-y-1 list-disc list-inside">
              <li>New appointments booked by AI</li>
              <li>Available time slots</li>
              <li>Booking confirmations</li>
              <li>Cancellations and rescheduling</li>
            </ul>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">Calendar Email</label>
            <input
              type="email"
              placeholder="your-calendar@gmail.com"
              className="input"
            />
          </div>

          <div className="flex gap-3 pt-4">
            <button disabled className="btn-primary flex-1 opacity-50 cursor-not-allowed">
              Connect with Google
            </button>
            <button onClick={onClose} className="btn-secondary flex-1">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default CalendarSetup;
