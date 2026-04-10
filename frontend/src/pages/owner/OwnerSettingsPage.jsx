import { useEffect, useState } from 'react';

import { ownerAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

const Section = ({ title, children }) => (
  <section className="bg-paper border border-ink/10 rounded-sm p-4 max-w-2xl">
    <h2 className="text-lg font-medium text-ink mb-3">{title}</h2>
    {children}
  </section>
);

const mask = (key) => {
  if (!key) return '—';
  if (key.length <= 4) return '****';
  return `****${key.slice(-4)}`;
};

const OwnerSettingsPage = () => {
  const { user } = useAuth();
  const { licenseStatus, licenseLastVerifiedAt, refresh } = useBootstrap();
  const [stats, setStats] = useState(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    ownerAPI.getDashboardStats().then(({ data }) => setStats(data));
  }, []);

  const handleReverify = async () => {
    setBusy(true);
    setMessage('');
    try {
      const { data } = await ownerAPI.reverifyLicense();
      setMessage(`License status: ${data.status}`);
      await refresh();
      const fresh = await ownerAPI.getDashboardStats();
      setStats(fresh.data);
    } catch (err) {
      setMessage('Re-verification failed. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">Settings</h1>

      <Section title="License">
        <dl className="text-sm space-y-1">
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Status:</dt>
            <dd className="capitalize">{licenseStatus || '—'}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Key:</dt>
            <dd>{mask(stats?.license_key_masked)}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Last verified:</dt>
            <dd>
              {licenseLastVerifiedAt
                ? new Date(licenseLastVerifiedAt).toLocaleString()
                : '—'}
            </dd>
          </div>
        </dl>
        <button onClick={handleReverify} disabled={busy} className={`${buttonClass} mt-3`}>
          {busy ? 'Re-verifying…' : 'Re-verify now'}
        </button>
        {message && <p className="text-sm mt-2">{message}</p>}
      </Section>

      <Section title="Account">
        <dl className="text-sm space-y-1">
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Email:</dt>
            <dd>{user?.email}</dd>
          </div>
          <div className="flex gap-2">
            <dt className="label-mono text-ink/60 w-32">Name:</dt>
            <dd>{user?.first_name} {user?.last_name}</dd>
          </div>
        </dl>
        <p className="text-xs text-ink/60 mt-2">
          Password change and additional account settings will be added in a
          future step.
        </p>
      </Section>
    </div>
  );
};

export default OwnerSettingsPage;
