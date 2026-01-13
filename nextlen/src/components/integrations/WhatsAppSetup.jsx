import { X, ExternalLink } from 'lucide-react';

const WhatsAppSetup = ({ onClose }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white dark:bg-gray-800 rounded-xl p-6 max-w-lg w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Setup WhatsApp Business</h3>
          <button onClick={onClose} className="text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300">
            <X size={24} />
          </button>
        </div>

        <div className="space-y-4">
          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-700 rounded-lg p-4">
            <p className="text-sm text-blue-800 dark:text-blue-300">
              WhatsApp Business API integration requires approval from Meta.
            </p>
          </div>

          <div>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
              1. You need a WhatsApp Business Account
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">
              2. Apply for WhatsApp Business API access
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
              3. Once approved, enter your credentials below
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">Phone Number ID</label>
            <input
              type="text"
              placeholder="Enter your phone number ID"
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2 text-gray-900 dark:text-gray-100">Access Token</label>
            <input
              type="password"
              placeholder="Enter your access token"
              className="input"
            />
          </div>

          <a
            href="https://business.whatsapp.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-2 text-primary-500 dark:text-primary-400 hover:underline text-sm"
          >
            <ExternalLink size={16} />
            Learn more about WhatsApp Business API
          </a>

          <div className="flex gap-3 pt-4">
            <button className="btn-primary flex-1">Connect</button>
            <button onClick={onClose} className="btn-secondary flex-1">
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WhatsAppSetup;
