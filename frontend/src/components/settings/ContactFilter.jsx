import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { X, Plus } from 'lucide-react';
import { autoReplyAPI } from '../../api/autoReply';

const ContactFilter = ({ channel, contactMode, contactList, onModeChange, onListChange }) => {
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);
  const [phoneInput, setPhoneInput] = useState('');
  const [recentContacts, setRecentContacts] = useState([]);
  const [selectedContact, setSelectedContact] = useState(null);
  const [loadingContacts, setLoadingContacts] = useState(false);

  const removeContact = (id) => {
    onListChange(contactList.filter(c => c !== id));
  };

  const openModal = async () => {
    setShowModal(true);
    setPhoneInput('');
    setSelectedContact(null);
    setLoadingContacts(true);
    try {
      const res = await autoReplyAPI.getContacts(channel);
      setRecentContacts(res.data.contacts || []);
    } catch {
      setRecentContacts([]);
    } finally {
      setLoadingContacts(false);
    }
  };

  const addContact = () => {
    const id = selectedContact || phoneInput.replace(/[\s\-+]/g, '');
    if (!id) return;
    if (!contactList.includes(id)) {
      onListChange([...contactList, id]);
    }
    setShowModal(false);
  };

  const showList = contactMode === 'all_except' || contactMode === 'only';

  return (
    <div>
      <div className="space-y-2">
        {['all', 'all_except', 'only'].map(mode => (
          <label key={mode} className="flex items-center gap-2 cursor-pointer">
            <input
              type="radio"
              name={`contact-mode-${channel}`}
              value={mode}
              checked={contactMode === mode}
              onChange={() => onModeChange(mode)}
              className="w-4 h-4 text-primary-500 focus:ring-primary-500"
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {t(`settings.contactMode${mode === 'all' ? 'All' : mode === 'all_except' ? 'AllExcept' : 'Only'}`)}
            </span>
          </label>
        ))}
      </div>

      {showList && (
        <div className="mt-3 space-y-2">
          {contactList.map(id => (
            <div key={id} className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
              <span className="text-sm text-gray-700 dark:text-gray-300">
                {id.startsWith('telegram_') ? id : `+${id}`}
              </span>
              <button onClick={() => removeContact(id)} className="text-gray-400 hover:text-red-500">
                <X size={16} />
              </button>
            </div>
          ))}
          <button
            onClick={openModal}
            className="flex items-center gap-1 text-sm text-primary-500 hover:text-primary-600"
          >
            <Plus size={16} />
            {t('settings.addContact')}
          </button>
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                {t('settings.addContactTitle')}
              </h3>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>

            <div className="mb-4">
              <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">
                {t('settings.enterPhone')}
              </label>
              <input
                type="text"
                value={phoneInput}
                onChange={e => { setPhoneInput(e.target.value); setSelectedContact(null); }}
                placeholder="+48..."
                className="w-full px-3 py-2 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
              />
            </div>

            {recentContacts.length > 0 && (
              <div className="mb-4">
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  {t('settings.orSelectRecent')}
                </p>
                <div className="max-h-48 overflow-y-auto space-y-1">
                  {recentContacts
                    .filter(c => !contactList.includes(c.id))
                    .map(c => (
                      <label key={c.id} className="flex items-start gap-2 p-2 rounded hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer">
                        <input
                          type="radio"
                          name="recent-contact"
                          checked={selectedContact === c.id}
                          onChange={() => { setSelectedContact(c.id); setPhoneInput(''); }}
                          className="mt-1 w-4 h-4 text-primary-500"
                        />
                        <div>
                          <div className="text-sm text-gray-700 dark:text-gray-300">{c.label}</div>
                          {c.last_message && (
                            <div className="text-xs text-gray-400 truncate max-w-[250px]">
                              {c.last_message}
                            </div>
                          )}
                        </div>
                      </label>
                    ))}
                </div>
              </div>
            )}

            {loadingContacts && (
              <p className="text-sm text-gray-400 mb-4">Loading...</p>
            )}

            <div className="flex justify-end gap-2">
              <button onClick={() => setShowModal(false)} className="btn-secondary text-sm">
                {t('settings.cancel')}
              </button>
              <button
                onClick={addContact}
                disabled={!phoneInput && !selectedContact}
                className="btn-primary text-sm disabled:opacity-50"
              >
                {t('settings.add')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default ContactFilter;
