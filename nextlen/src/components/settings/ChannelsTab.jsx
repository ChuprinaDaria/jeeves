import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { Loader2 } from 'lucide-react';
import api from '../../api/axios';
import { autoReplyAPI } from '../../api/autoReply';
import ChannelCard from './ChannelCard';

const CHANNEL_DEFS = [
  {
    key: 'whatsapp_bridge',
    label: 'WhatsApp',
    getConnectionInfo: (data) => data.bridgePhone ? `+${data.bridgePhone}` : null,
    isConnected: (data) => data.bridgeStatus === 'connected',
  },
  {
    key: 'telegram',
    label: 'Telegram',
    getConnectionInfo: () => null,
    isConnected: (data) => data.telegramEnabled,
  },
];

const ChannelsTab = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [channelData, setChannelData] = useState({});
  const [configs, setConfigs] = useState({});

  useEffect(() => {
    const loadData = async () => {
      try {
        const [bridgeRes, meRes, autoReplyRes] = await Promise.all([
          api.get('/clients/whatsapp/bridge/config/').catch(() => ({ data: {} })),
          api.get('/clients/me/').catch(() => ({ data: {} })),
          autoReplyAPI.list().catch(() => ({ data: { results: [] } })),
        ]);

        setChannelData({
          bridgeStatus: bridgeRes.data.whatsapp_bridge_status,
          bridgePhone: bridgeRes.data.whatsapp_bridge_phone,
          telegramEnabled: meRes.data.telegram_enabled,
        });

        const configMap = {};
        for (const cfg of (autoReplyRes.data.results || [])) {
          configMap[cfg.channel] = cfg;
        }
        setConfigs(configMap);
      } catch (err) {
        console.error('Failed to load channel data:', err);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex justify-center py-12">
        <Loader2 className="animate-spin text-gray-400" size={32} />
      </div>
    );
  }

  const connectedChannels = CHANNEL_DEFS.filter(ch => ch.isConnected(channelData));

  if (connectedChannels.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        {t('settings.noChannelsConnected')}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <p className="text-sm text-gray-500 dark:text-gray-400">
        {t('settings.channelsSubtitle')}
      </p>
      {connectedChannels.map(ch => (
        <ChannelCard
          key={ch.key}
          channel={ch.key}
          channelLabel={ch.label}
          connectionInfo={ch.getConnectionInfo(channelData)}
          initialConfig={configs[ch.key] || null}
        />
      ))}
    </div>
  );
};

export default ChannelsTab;
