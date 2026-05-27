import { useState } from 'react';
import { useSearchParams, useNavigate, Navigate } from 'react-router-dom';
import api from '../api/axios';

const inputClass =
  'w-full px-3 py-2 border border-ink/20 rounded-sm bg-paper focus:outline-none focus:border-iris text-lg tracking-wider';

const buttonClass =
  'w-full px-4 py-2 bg-ink text-cream rounded-sm hover:bg-ink/90 disabled:opacity-50';

const ClientLoginPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [tagInput, setTagInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // /l?tag=xxx → redirect на /l/xxx/dashboard (зворотна сумісність)
  const tagFromQuery = searchParams.get('tag');
  if (tagFromQuery) {
    return <Navigate to={`/l/${tagFromQuery}/dashboard`} replace />;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    const tag = tagInput.trim();
    if (!tag) return;

    setLoading(true);
    setError(null);

    try {
      const response = await api.get('/clients/me/', {
        headers: { 'X-Client-Token': tag },
      });
      if (response.data) {
        navigate(`/l/${tag}/dashboard`);
      }
    } catch (err) {
      const status = err.response?.status;
      if (status === 404 || status === 401 || status === 403) {
        setError('Invalid access code. Please check and try again.');
      } else {
        setError(err.response?.data?.error || 'Something went wrong. Please try again.');
      }
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="max-w-md w-full bg-paper border border-ink/10 rounded-sm p-6 space-y-4"
      >
        <div className="mb-4">
          <div className="label-mono text-ink/60">Jeeves</div>
          <h1 className="text-2xl font-semibold text-ink">Client portal</h1>
          <p className="text-sm text-fog mt-1">Enter your access code to continue</p>
        </div>

        <div>
          <label className="block text-sm mb-1">Access Code</label>
          <input
            className={inputClass}
            type="text"
            value={tagInput}
            onChange={(e) => {
              setTagInput(e.target.value);
              if (error) setError(null);
            }}
            placeholder="Enter your code..."
            autoFocus
            autoComplete="off"
            disabled={loading}
          />
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <button
          type="submit"
          className={buttonClass}
          disabled={loading || !tagInput.trim()}
        >
          {loading ? 'Checking...' : 'Continue'}
        </button>

        <p className="text-sm text-fog text-center pt-2">
          Your access code was provided by your administrator
        </p>
      </form>
    </div>
  );
};

export default ClientLoginPage;
