import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { setupAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-paper focus:outline-none focus:border-iris';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

const LicenseStep = ({ onDone }) => {
  const [key, setKey] = useState('');
  const [status, setStatus] = useState(null); // 'valid' | 'grace' | null
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { refresh: refreshBootstrap } = useBootstrap();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setStatus(null);
    setLoading(true);
    try {
      const { data } = await setupAPI.saveLicense(key);
      setStatus(data.status);
    } catch (err) {
      const body = err?.response?.data;
      if (body?.error === 'invalid_key') {
        setError(`Gumroad rejected the key: ${body.message || 'not found'}.`);
      } else {
        setError('Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleContinue = async () => {
    setLoading(true);
    try {
      await setupAPI.complete();
      await refreshBootstrap();
      onDone();
    } catch (err) {
      setError('Could not complete setup. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-paper border border-ink/10 rounded-sm p-6 space-y-4"
    >
      <h2 className="text-lg font-medium text-ink">Enter your Gumroad license key</h2>
      <p className="text-sm text-ink/70">
        You'll find this in the Gumroad email you received after purchase.
      </p>

      <div>
        <label className="block text-sm mb-1">License key</label>
        <input
          className={inputClass}
          type="text"
          required
          value={key}
          onChange={(e) => setKey(e.target.value)}
          disabled={status === 'valid' || status === 'grace'}
        />
      </div>

      {error && <p className="text-red-600 text-sm">{error}</p>}

      {status === 'valid' && (
        <p className="text-green-700 text-sm">
          ✓ License verified. Click Continue to finish setup.
        </p>
      )}

      {status === 'grace' && (
        <p className="text-yellow-700 text-sm">
          ⚠ We couldn't reach Gumroad right now. Your key was saved and we'll
          retry automatically. You have a 7-day grace period.
        </p>
      )}

      {!status && (
        <button type="submit" className={buttonClass} disabled={loading}>
          {loading ? 'Verifying…' : 'Verify key'}
        </button>
      )}

      {(status === 'valid' || status === 'grace') && (
        <button
          type="button"
          className={buttonClass}
          onClick={handleContinue}
          disabled={loading}
        >
          {loading ? 'Finishing…' : 'Continue →'}
        </button>
      )}
    </form>
  );
};

const TabBar = ({ tab, onTabChange }) => {
  const base = 'flex-1 py-2 text-sm font-medium text-center transition-colors';
  const active = `${base} text-ink border-b-2 border-ink`;
  const inactive = `${base} text-ink/40 hover:text-ink/60`;

  return (
    <div className="flex border-b border-ink/10 mb-6">
      <button type="button" className={tab === 'setup' ? active : inactive} onClick={() => onTabChange('setup')}>
        Setup
      </button>
      <button type="button" className={tab === 'login' ? active : inactive} onClick={() => onTabChange('login')}>
        Login
      </button>
    </div>
  );
};

const LoginTab = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await login(email, password);
      const role = data?.user?.role;
      if (role !== 'owner') {
        setError('Access denied: owner role required.');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        setLoading(false);
        return;
      }
      navigate('/owner/dashboard');
    } catch {
      setError('Invalid email or password.');
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-paper border border-ink/10 rounded-sm p-6 space-y-4">
      <h2 className="text-lg font-medium text-ink">Owner login</h2>
      <div>
        <label className="block text-sm mb-1">Email</label>
        <input className={inputClass} type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
      </div>
      <div>
        <label className="block text-sm mb-1">Password</label>
        <input className={inputClass} type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
      </div>
      {error && <p className="text-red-600 text-sm">{error}</p>}
      <button type="submit" className={buttonClass} disabled={loading}>
        {loading ? 'Signing in…' : 'Sign in'}
      </button>
    </form>
  );
};

const SetupWizard = () => {
  const navigate = useNavigate();
  const auth = useAuth();
  const setUserDirect = auth.setUserDirect;
  const [tab, setTab] = useState('setup');
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmitStep1 = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const { data } = await setupAPI.createOwner(form);
      localStorage.setItem('access_token', data.access);
      localStorage.setItem('refresh_token', data.refresh);
      if (setUserDirect) setUserDirect(data.user);
      setStep(2);
    } catch (err) {
      const status = err?.response?.status;
      const body = err?.response?.data;
      if (status === 409 && body?.error === 'owner_exists') {
        setTab('login');
      } else if (status === 409 && body?.error === 'email_taken') {
        setError('An account with this email already exists.');
      } else if (status === 400 && body?.password) {
        setError('Password must be at least 8 characters.');
      } else if (status === 400 && body?.email) {
        setError('Please enter a valid email address.');
      } else {
        setError('Could not create account. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <div className="max-w-md w-full">
        <div className="mb-2 text-center">
          <div className="label-mono text-ink/60">Jeeves</div>
        </div>

        {step === 1 && (
          <>
            <TabBar tab={tab} onTabChange={setTab} />

            {tab === 'setup' && (
              <form
                onSubmit={handleSubmitStep1}
                className="bg-paper border border-ink/10 rounded-sm p-6 space-y-4"
              >
                <h2 className="text-lg font-medium text-ink">
                  Create your owner account
                </h2>

                <div>
                  <label className="block text-sm mb-1">First name</label>
                  <input
                    className={inputClass}
                    type="text"
                    required
                    value={form.first_name}
                    onChange={(e) => setForm({ ...form, first_name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1">Last name</label>
                  <input
                    className={inputClass}
                    type="text"
                    required
                    value={form.last_name}
                    onChange={(e) => setForm({ ...form, last_name: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1">Email</label>
                  <input
                    className={inputClass}
                    type="email"
                    required
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                  />
                </div>
                <div>
                  <label className="block text-sm mb-1">
                    Password (min 8 chars)
                  </label>
                  <input
                    className={inputClass}
                    type="password"
                    required
                    minLength={8}
                    value={form.password}
                    onChange={(e) => setForm({ ...form, password: e.target.value })}
                  />
                </div>

                {error && <p className="text-red-600 text-sm">{error}</p>}

                <button type="submit" className={buttonClass} disabled={loading}>
                  {loading ? 'Creating…' : 'Continue →'}
                </button>
              </form>
            )}

            {tab === 'login' && <LoginTab />}
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="text-2xl font-semibold text-ink text-center mb-6">
              Step 2 of 2
            </h1>
            <LicenseStep onDone={() => navigate('/owner/dashboard')} />
          </>
        )}
      </div>
    </div>
  );
};

export default SetupWizard;
