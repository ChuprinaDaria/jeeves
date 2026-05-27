import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { setupAPI } from '../../api/owner';
import { useAuth } from '../../context/AuthContext';

const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-paper focus:outline-none focus:border-iris';

const buttonClass =
  'px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

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
        {loading ? 'Signing in...' : 'Sign in'}
      </button>
    </form>
  );
};

const SetupWizard = () => {
  const navigate = useNavigate();
  const auth = useAuth();
  const setUserDirect = auth.setUserDirect;
  const [tab, setTab] = useState('setup');
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
      await setupAPI.complete();
      navigate('/owner/dashboard');
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
              {loading ? 'Creating...' : 'Create account'}
            </button>
          </form>
        )}

        {tab === 'login' && <LoginTab />}
      </div>
    </div>
  );
};

export default SetupWizard;
