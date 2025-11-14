import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageCircle, Send } from 'lucide-react';

const SetupInstructionsPage = () => {
  const { t } = useTranslation();
  const [activeIntegration, setActiveIntegration] = useState('whatsapp'); // 'whatsapp', 'telegram', etc.

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('setupInstructions.title')}</h1>
        <p className="text-gray-600">{t('setupInstructions.subtitle')}</p>
      </div>

      {/* Integration Selector */}
      <div className="flex gap-4 border-b border-gray-200">
        <button
          onClick={() => setActiveIntegration('whatsapp')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeIntegration === 'whatsapp'
              ? 'border-green-600 text-green-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          <MessageCircle size={20} />
          WhatsApp
        </button>
        <button
          onClick={() => setActiveIntegration('telegram')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 opacity-50 cursor-not-allowed ${
            activeIntegration === 'telegram'
              ? 'border-blue-600 text-blue-600'
              : 'border-transparent text-gray-500'
          }`}
          disabled
        >
          <Send size={20} />
          Telegram (Coming Soon)
        </button>
      </div>

      {/* WhatsApp Instructions */}
      {activeIntegration === 'whatsapp' && (
        <div className="card max-w-4xl">
          <h2 className="text-xl font-semibold mb-4">{t('setupInstructions.whatsappSetup')}</h2>
          
          <div className="prose max-w-none">
            <div className="bg-blue-50 border-l-4 border-blue-500 p-4 mb-6">
              <p className="text-blue-800">
                {t('setupInstructions.whatsappIntro')}
              </p>
            </div>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 1 — Create a Meta Business Account</h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>Visit: <a href="https://business.facebook.com" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">https://business.facebook.com</a></li>
              <li>Log in with your Facebook account</li>
              <li>If asked — create a Business Manager</li>
              <li>Complete the business details (company name, address, phone number)</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 2 — Create a WhatsApp App</h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>Open Meta Developers: <a href="https://developers.facebook.com/apps" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">https://developers.facebook.com/apps</a></li>
              <li>Click "Create App"</li>
              <li>Choose <strong>Other → Business → WhatsApp</strong></li>
              <li>Set the app name (ex: "Restaurant WhatsApp")</li>
              <li>Confirm creation</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 3 — Add WhatsApp API to your App</h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>Open your newly created app</li>
              <li>In the left menu select "WhatsApp" → "Getting Started"</li>
              <li>You will see:
                <ul className="list-circle pl-6 mt-2 space-y-1">
                  <li>Temporary token</li>
                  <li>Test phone number</li>
                  <li>Phone Number ID</li>
                  <li>WhatsApp Business Account ID (WABA)</li>
                </ul>
              </li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 4 — Add your own phone number</h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>Open WhatsApp Manager: <a href="https://business.facebook.com/wa/manage" target="_blank" rel="noopener noreferrer" className="text-primary-600 hover:underline">https://business.facebook.com/wa/manage</a></li>
              <li>Go to <strong>Phone Numbers</strong></li>
              <li>Click "Add Phone Number"</li>
              <li>Enter your business phone number</li>
              <li>Confirm by SMS or voice call</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 5 — Generate a permanent access token</h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>In Business Manager open: <strong>Business Settings → Users → System Users</strong></li>
              <li>Create a system user (role: Admin)</li>
              <li>Create a token for this system user</li>
              <li>Select your app</li>
              <li>Give permissions:
                <ul className="list-circle pl-6 mt-2 space-y-1">
                  <li><code className="bg-gray-100 px-2 py-1 rounded">whatsapp_business_messaging</code></li>
                  <li><code className="bg-gray-100 px-2 py-1 rounded">whatsapp_business_management</code></li>
                </ul>
              </li>
              <li>Generate a permanent access token</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 6 — Set up Webhook</h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-4">
              <li>Open your app in Meta Developers</li>
              <li>Go to: <strong>WhatsApp → Configuration → Webhooks</strong></li>
              <li>Enter:</li>
            </ul>
            <div className="bg-gray-100 p-4 rounded-lg font-mono text-sm mb-4 ml-6">
              <p><strong>Callback URL:</strong></p>
              <p className="text-xs break-all">https://api.nexelin.com/api/clients/whatsapp/meta/webhook/</p>
              <p className="mt-3"><strong>Verify Token:</strong></p>
              <p className="text-xs">(you will receive your token from Nexelin)</p>
            </div>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>Click "Verify and Save"</li>
              <li>Click "Manage Subscriptions" and enable:
                <ul className="list-circle pl-6 mt-2 space-y-1">
                  <li><code className="bg-gray-100 px-2 py-1 rounded">messages</code></li>
                  <li><code className="bg-gray-100 px-2 py-1 rounded">message_template_status_update</code></li>
                  <li>(optional) <code className="bg-gray-100 px-2 py-1 rounded">phone_number_quality_update</code></li>
                </ul>
              </li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3">✅ Step 7 — Copy your data into Nexelin portal</h3>
            <p className="text-gray-700 mb-4">
              In your Nexelin client account, go to <strong>Integrations</strong> page and fill in the following fields:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 mb-6">
              <li>Meta WABA ID</li>
              <li>Meta App ID</li>
              <li>Meta App Secret</li>
              <li>Meta Access Token</li>
              <li>Meta Phone Number ID</li>
              <li>Your business WhatsApp number</li>
              <li>Webhook Verify Token</li>
              <li>Click <strong>Save</strong></li>
            </ul>

            <div className="bg-green-50 border-l-4 border-green-500 p-4 mt-6">
              <p className="text-green-800 font-semibold">
                🎉 Done! Your WhatsApp Business API is now connected and can send + receive messages through Nexelin.
              </p>
            </div>

            <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 mt-6">
              <p className="text-yellow-800">
                <strong>Note:</strong> WhatsApp Business API requires approval from Meta. Make sure your business account is verified and approved before setting up the integration.
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SetupInstructionsPage;

