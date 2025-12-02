import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { MessageCircle, Send, CheckCircle2, PartyPopper, AlertCircle, Building2, Smartphone, Key, Webhook, Settings, Copy, BookOpen, Globe2 } from 'lucide-react';
import PromptBook from '../components/training/PromptBook';
import ExtensionData from '../components/training/ExtensionData';

const SetupInstructionsPage = () => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('integrations'); // 'integrations', 'promptbook', 'extensionData'
  const [activeIntegration, setActiveIntegration] = useState('whatsapp'); // 'whatsapp', 'telegram', etc.

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100">{t('setupInstructions.title')}</h1>
        <p className="text-gray-600 dark:text-gray-400">{t('setupInstructions.subtitle')}</p>
      </div>

      {/* Main Tabs */}
      <div className="flex gap-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveTab('integrations')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeTab === 'integrations'
              ? 'border-primary-600 dark:border-primary-400 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          <MessageCircle size={20} />
          {t('setupInstructions.integrations') || 'Integrations'}
        </button>
        <button
          onClick={() => setActiveTab('promptbook')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeTab === 'promptbook'
              ? 'border-primary-600 dark:border-primary-400 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          <BookOpen size={20} />
          {t('setupInstructions.promptBook') || 'Prompt Book'}
        </button>
        <button
          onClick={() => setActiveTab('extensionData')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeTab === 'extensionData'
              ? 'border-primary-600 dark:border-primary-400 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          <Globe2 size={20} />
          {t('setupInstructions.extensionData') || 'Extension data'}
        </button>
      </div>

      {/* Prompt Book Tab */}
      {activeTab === 'promptbook' && <PromptBook />}

      {/* Extension Data Tab */}
      {activeTab === 'extensionData' && <ExtensionData />}

      {/* Integration Selector */}
      {activeTab === 'integrations' && (
        <>
          <div className="flex gap-4 border-b border-gray-200 dark:border-gray-700">
        <button
          onClick={() => setActiveIntegration('whatsapp')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeIntegration === 'whatsapp'
              ? 'border-green-600 dark:border-green-400 text-green-600 dark:text-green-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          <MessageCircle size={20} />
          WhatsApp
        </button>
        <button
          onClick={() => setActiveIntegration('telegram')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeIntegration === 'telegram'
              ? 'border-blue-600 dark:border-blue-400 text-blue-600 dark:text-blue-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          <Send size={20} />
          Telegram
        </button>
        <button
          onClick={() => setActiveIntegration('email')}
          className={`pb-3 px-1 border-b-2 font-medium transition-colors flex items-center gap-2 ${
            activeIntegration === 'email'
              ? 'border-indigo-600 dark:border-indigo-400 text-indigo-600 dark:text-indigo-400'
              : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          }`}
        >
          <Settings size={20} />
          Email SMTP
        </button>
      </div>

      {/* WhatsApp Instructions */}
      {activeIntegration === 'whatsapp' && (
        <div className="card max-w-4xl">
          <h2 className="text-xl font-semibold mb-4">{t('setupInstructions.whatsappSetup')}</h2>
          
          <div className="prose max-w-none">
            <div className="bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500 dark:border-blue-400 p-4 mb-6">
              <p className="text-blue-800 dark:text-blue-300">
                {t('setupInstructions.whatsappIntro')}
              </p>
            </div>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 1 — Create a Meta Business Account
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Visit: <a href="https://business.facebook.com" target="_blank" rel="noopener noreferrer" className="text-primary-600 dark:text-primary-400 hover:underline">https://business.facebook.com</a></li>
              <li>Log in with your Facebook account</li>
              <li>If asked — create a Business Manager</li>
              <li>Complete the business details (company name, address, phone number)</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 2 — Create a WhatsApp App
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Open Meta Developers: <a href="https://developers.facebook.com/apps" target="_blank" rel="noopener noreferrer" className="text-primary-600 dark:text-primary-400 hover:underline">https://developers.facebook.com/apps</a></li>
              <li>Click "Create App"</li>
              <li>Choose <strong>Other → Business → WhatsApp</strong></li>
              <li>Set the app name (ex: "Restaurant WhatsApp")</li>
              <li>Confirm creation</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 3 — Add WhatsApp API to your App
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
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

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 4 — Add your own phone number
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Open WhatsApp Manager: <a href="https://business.facebook.com/wa/manage" target="_blank" rel="noopener noreferrer" className="text-primary-600 dark:text-primary-400 hover:underline">https://business.facebook.com/wa/manage</a></li>
              <li>Go to <strong>Phone Numbers</strong></li>
              <li>Click "Add Phone Number"</li>
              <li>Enter your business phone number</li>
              <li>Confirm by SMS or voice call</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2">
              <CheckCircle2 size={20} className="text-green-600" />
              Step 5 — Generate a permanent access token
            </h3>
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

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2">
              <CheckCircle2 size={20} className="text-green-600" />
              Step 6 — Set up Webhook
            </h3>
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

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2">
              <CheckCircle2 size={20} className="text-green-600" />
              Step 7 — Copy your data into Nexelin portal
            </h3>
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
              <p className="text-green-800 font-semibold flex items-center gap-2">
                <PartyPopper size={20} className="text-green-600" />
                Done! Your WhatsApp Business API is now connected and can send + receive messages through Nexelin.
              </p>
            </div>

            <div className="bg-yellow-50 border-l-4 border-yellow-500 p-4 mt-6">
              <p className="text-yellow-800 flex items-start gap-2">
                <AlertCircle size={20} className="text-yellow-600 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Note:</strong> WhatsApp Business API requires approval from Meta. Make sure your business account is verified and approved before setting up the integration.
                </span>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Telegram Instructions */}
      {activeIntegration === 'telegram' && (
        <div className="card max-w-4xl">
          <h2 className="text-xl font-semibold mb-4">{t('setupInstructions.telegramSetup')}</h2>
          
          <div className="prose max-w-none">
            <div className="bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500 dark:border-blue-400 p-4 mb-6">
              <p className="text-blue-800 dark:text-blue-300">
                {t('setupInstructions.telegramIntro')}
              </p>
            </div>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 1 — Create a Telegram Bot
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Open Telegram app on your phone or desktop</li>
              <li>Search for <strong>@BotFather</strong> in Telegram</li>
              <li>Start a conversation with BotFather</li>
              <li>Send the command: <code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">/newbot</code></li>
              <li>Follow the instructions:
                <ul className="list-circle pl-6 mt-2 space-y-1">
                  <li>Enter a name for your bot (e.g., "My Restaurant Bot")</li>
                  <li>Enter a username for your bot (must end with "bot", e.g., "my_restaurant_bot")</li>
                </ul>
              </li>
              <li>BotFather will send you a <strong>Bot Token</strong> — save it securely!</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 2 — Configure Bot Settings (Optional)
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>You can customize your bot with BotFather commands:
                <ul className="list-circle pl-6 mt-2 space-y-1">
                  <li><code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">/setdescription</code> — Set bot description</li>
                  <li><code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">/setabouttext</code> — Set about text</li>
                  <li><code className="bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">/setuserpic</code> — Set bot profile picture</li>
                </ul>
              </li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 3 — Add Bot Token to Nexelin
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Go to your Nexelin client portal</li>
              <li>Navigate to <strong>Integrations</strong> page</li>
              <li>Find the <strong>Telegram</strong> section</li>
              <li>Click <strong>Configure</strong> button</li>
              <li>Enable Telegram integration</li>
              <li>Paste your Bot Token in the <strong>Bot Token</strong> field</li>
              <li>Click <strong>Save</strong></li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 4 — Webhook Configuration
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              Nexelin automatically sets up the webhook for your bot. The webhook URL will be displayed after saving your bot token.
            </p>
            <div className="bg-gray-100 dark:bg-gray-700 p-4 rounded-lg font-mono text-sm mb-4">
              <p><strong>Webhook URL:</strong></p>
              <p className="text-xs break-all">https://api.nexelin.com/api/clients/telegram/webhook/</p>
            </div>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>This webhook is automatically configured when you save your bot token</li>
              <li>You can copy the webhook URL if needed for reference</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 5 — Test Your Bot
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Open Telegram and search for your bot by username</li>
              <li>Start a conversation with your bot</li>
              <li>Send a test message</li>
              <li>Your AI assistant should respond automatically!</li>
            </ul>

            <div className="bg-green-50 dark:bg-green-900/30 border-l-4 border-green-500 dark:border-green-400 p-4 mt-6">
              <p className="text-green-800 dark:text-green-300 font-semibold flex items-center gap-2">
                <PartyPopper size={20} className="text-green-600 dark:text-green-400" />
                {t('setupInstructions.telegramDone')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Email SMTP Instructions */}
      {activeIntegration === 'email' && (
        <div className="card max-w-4xl">
          <h2 className="text-xl font-semibold mb-4">{t('setupInstructions.emailSetup')}</h2>
          
          <div className="prose max-w-none">
            <div className="bg-indigo-50 dark:bg-indigo-900/30 border-l-4 border-indigo-500 dark:border-indigo-400 p-4 mb-6">
              <p className="text-indigo-800 dark:text-indigo-300">
                {t('setupInstructions.emailIntro')}
              </p>
            </div>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 1 — Choose Your Email Provider
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              Nexelin supports all major email providers. Here are the most common settings:
            </p>
            <div className="bg-gray-100 dark:bg-gray-700 p-4 rounded-lg mb-6">
              <div className="space-y-3 text-sm">
                <div>
                  <strong className="text-gray-900 dark:text-gray-100">Gmail:</strong>
                  <ul className="list-disc pl-6 mt-1 space-y-1 text-gray-700 dark:text-gray-300">
                    <li>SMTP Host: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">smtp.gmail.com</code></li>
                    <li>SMTP Port: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">587</code> (TLS) or <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">465</code> (SSL)</li>
                    <li>Use TLS: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">Yes</code> (for port 587)</li>
                    <li>Username: Your Gmail address</li>
                    <li>Password: <strong>App Password</strong> (not your regular password)</li>
                  </ul>
                </div>
                <div>
                  <strong className="text-gray-900 dark:text-gray-100">Outlook/Office 365:</strong>
                  <ul className="list-disc pl-6 mt-1 space-y-1 text-gray-700 dark:text-gray-300">
                    <li>SMTP Host: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">smtp-mail.outlook.com</code></li>
                    <li>SMTP Port: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">587</code></li>
                    <li>Use TLS: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">Yes</code></li>
                    <li>Username: Your Outlook email address</li>
                    <li>Password: Your Outlook password</li>
                  </ul>
                </div>
                <div>
                  <strong className="text-gray-900 dark:text-gray-100">Yahoo:</strong>
                  <ul className="list-disc pl-6 mt-1 space-y-1 text-gray-700 dark:text-gray-300">
                    <li>SMTP Host: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">smtp.mail.yahoo.com</code></li>
                    <li>SMTP Port: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">587</code> (TLS) or <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">465</code> (SSL)</li>
                    <li>Use TLS: <code className="bg-gray-200 dark:bg-gray-600 px-1 rounded">Yes</code> (for port 587)</li>
                    <li>Username: Your Yahoo email address</li>
                    <li>Password: Your Yahoo password</li>
                  </ul>
                </div>
              </div>
            </div>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 2 — Generate App Password (Gmail)
            </h3>
            <p className="text-gray-700 dark:text-gray-300 mb-4">
              If you're using Gmail, you need to create an App Password instead of using your regular password:
            </p>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Go to your Google Account: <a href="https://myaccount.google.com" target="_blank" rel="noopener noreferrer" className="text-primary-600 dark:text-primary-400 hover:underline">https://myaccount.google.com</a></li>
              <li>Navigate to <strong>Security</strong> → <strong>2-Step Verification</strong></li>
              <li>Scroll down to <strong>App passwords</strong></li>
              <li>Select <strong>Mail</strong> and <strong>Other (Custom name)</strong></li>
              <li>Enter "Nexelin AI" as the app name</li>
              <li>Click <strong>Generate</strong></li>
              <li>Copy the 16-character password (you'll use this in Nexelin)</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 3 — Configure SMTP in Nexelin
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Go to your Nexelin client portal</li>
              <li>Navigate to <strong>Integrations</strong> page</li>
              <li>Find the <strong>Email</strong> section</li>
              <li>Click <strong>Configure</strong> button</li>
              <li>Enable Email SMTP</li>
              <li>Fill in the following fields:
                <ul className="list-circle pl-6 mt-2 space-y-1">
                  <li><strong>SMTP Host:</strong> Your email provider's SMTP server</li>
                  <li><strong>SMTP Port:</strong> Usually 587 (TLS) or 465 (SSL)</li>
                  <li><strong>Use TLS:</strong> Enable for port 587, disable for port 465</li>
                  <li><strong>SMTP Username:</strong> Your email address</li>
                  <li><strong>SMTP Password:</strong> Your password or App Password (for Gmail)</li>
                  <li><strong>From Email Address:</strong> Email address that will appear as sender</li>
                  <li><strong>From Name:</strong> Name that will appear as sender (optional)</li>
                </ul>
              </li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 4 — Test Connection
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>After filling in all fields, click <strong>Test Connection</strong> button</li>
              <li>Nexelin will verify your SMTP settings</li>
              <li>If successful, you'll see a confirmation message</li>
              <li>If failed, check your settings and try again</li>
            </ul>

            <h3 className="text-lg font-semibold mt-6 mb-3 flex items-center gap-2 text-gray-900 dark:text-gray-100">
              <CheckCircle2 size={20} className="text-green-600 dark:text-green-400" />
              Step 5 — Save Configuration
            </h3>
            <ul className="list-disc pl-6 space-y-2 text-gray-700 dark:text-gray-300 mb-6">
              <li>Once the connection test passes, click <strong>Save</strong></li>
              <li>Your email integration is now active!</li>
              <li>You can now use email commands in the Sandbox chat</li>
            </ul>

            <div className="bg-green-50 dark:bg-green-900/30 border-l-4 border-green-500 dark:border-green-400 p-4 mt-6">
              <p className="text-green-800 dark:text-green-300 font-semibold flex items-center gap-2">
                <PartyPopper size={20} className="text-green-600 dark:text-green-400" />
                {t('setupInstructions.emailDone')}
              </p>
            </div>

            <div className="bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500 dark:border-blue-400 p-4 mt-6">
              <p className="text-blue-800 dark:text-blue-300 flex items-start gap-2">
                <AlertCircle size={20} className="text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>{t('setupInstructions.emailNoteTitle')}:</strong> {t('setupInstructions.emailNote')}
                </span>
              </p>
            </div>
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};

export default SetupInstructionsPage;

