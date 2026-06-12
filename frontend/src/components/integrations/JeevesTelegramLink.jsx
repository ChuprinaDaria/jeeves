import { useEffect, useState, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { PaperPlaneTilt, LinkSimple, LinkBreak, CopySimple, Sparkle } from '@phosphor-icons/react';
import api from '../../api/axios';
import Card from '../ui/Card';

/**
 * Owner ↔ Jeeves direct line in Telegram.
 *
 * Generates a one-time code; the owner sends `/jeeves <code>` to their own
 * client bot, after which that chat talks to Jeeves (assistant scope) instead
 * of the customer-facing consultant.
 */
const JeevesTelegramLink = () => {
  const { t } = useTranslation();
  const [status, setStatus] = useState(null); // { linked, bot_configured }
  const [code, setCode] = useState(null);     // { code, command, expires_in }
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.get('/clients/owner-telegram/');
      setStatus(res.data);
    } catch { /* leave null */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const generate = async () => {
    setBusy(true);
    try {
      const res = await api.post('/clients/owner-telegram/');
      setCode(res.data);
    } catch { /* error UI below */ } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    setBusy(true);
    try {
      await api.delete('/clients/owner-telegram/');
      setCode(null);
      await load();
    } finally {
      setBusy(false);
    }
  };

  const copy = () => {
    navigator.clipboard?.writeText(code.command);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  if (!status) return null;

  return (
    <Card className="mb-8">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="flex items-start gap-3">
          <div className="w-10 h-10 rounded-lg border-[1.5px] border-iris text-iris flex items-center justify-center shrink-0">
            <Sparkle size={20} weight="light" />
          </div>
          <div>
            <div className="text-[15px] font-semibold text-ink flex items-center gap-2">
              {t('integrations.jeevesTg.title')}
              {status.linked && (
                <span className="font-mono text-[10px] uppercase tracking-wider text-sage
                                 border-[1.5px] border-sage rounded px-1.5 py-0.5">
                  {t('integrations.jeevesTg.linked')}
                </span>
              )}
            </div>
            <p className="text-[13px] text-slate mt-1 max-w-xl leading-relaxed">
              {t('integrations.jeevesTg.description')}
            </p>
            {!status.bot_configured && (
              <p className="font-mono text-[11px] text-amber mt-2 uppercase tracking-wide">
                {t('integrations.jeevesTg.needsBot')}
              </p>
            )}
            {code && !status.linked && (
              <div className="mt-3 flex items-center gap-2 flex-wrap">
                <code className="px-3 py-2 rounded-lg bg-linen border-[1.5px] border-rule
                                 font-mono text-[14px] text-ink select-all">
                  {code.command}
                </code>
                <button
                  onClick={copy}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border-[1.5px] border-rule
                             text-[12px] text-slate hover:text-ink hover:bg-mist transition-colors bg-transparent"
                >
                  <CopySimple size={14} weight="light" />
                  {copied ? t('integrations.jeevesTg.copied') : t('integrations.jeevesTg.copy')}
                </button>
                <span className="font-mono text-[11px] text-fog">
                  {t('integrations.jeevesTg.sendHint')}
                </span>
              </div>
            )}
          </div>
        </div>

        <div className="shrink-0">
          {status.linked ? (
            <button
              onClick={unlink}
              disabled={busy}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border-[1.5px] border-rose text-rose
                         text-[12px] font-medium hover:bg-rose-soft/30 transition-colors bg-transparent disabled:opacity-40"
            >
              <LinkBreak size={14} weight="light" />
              {t('integrations.jeevesTg.unlink')}
            </button>
          ) : (
            <button
              onClick={generate}
              disabled={busy || !status.bot_configured}
              className="flex items-center gap-1.5 px-3 py-2 rounded-lg border-[1.5px] border-iris text-iris
                         text-[12px] font-medium hover:bg-iris-soft/30 transition-colors bg-transparent disabled:opacity-40"
            >
              {code ? <PaperPlaneTilt size={14} weight="light" /> : <LinkSimple size={14} weight="light" />}
              {code ? t('integrations.jeevesTg.regenerate') : t('integrations.jeevesTg.generate')}
            </button>
          )}
        </div>
      </div>
    </Card>
  );
};

export default JeevesTelegramLink;
