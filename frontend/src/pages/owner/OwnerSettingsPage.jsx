import { Link } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';

const Section = ({ title, children }) => (
  <section className="bg-paper border border-ink/10 rounded-sm p-4 max-w-2xl">
    <h2 className="text-lg font-medium text-ink mb-3">{title}</h2>
    {children}
  </section>
);

const OwnerSettingsPage = () => {
  const { user } = useAuth();

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-semibold text-ink">Settings</h1>

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

      <Section title="AI behaviour defaults">
        <p className="text-sm text-ink/70 mb-2">
          Edit temperature, max tokens, context chunks, supported languages
          and the default greeting.
        </p>
        <Link
          to="/owner/settings/defaults"
          className="text-ink underline text-sm"
        >
          Open defaults editor →
        </Link>
      </Section>
    </div>
  );
};

export default OwnerSettingsPage;
