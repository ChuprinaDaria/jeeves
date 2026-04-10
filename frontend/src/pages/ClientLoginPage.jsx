import { useState } from 'react';
import { useSearchParams, useNavigate, Navigate } from 'react-router-dom';
import { Loader2, LogIn, KeyRound } from 'lucide-react';
import api from '../api/axios';

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

  // Без тегу — сторінка логіна
  const handleSubmit = async (e) => {
    e.preventDefault();
    const tag = tagInput.trim();
    if (!tag) return;

    setLoading(true);
    setError(null);

    try {
      const response = await api.get('/clients/me/', {
        headers: { 'X-Client-Token': tag }
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
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 dark:from-gray-950 dark:via-gray-900 dark:to-indigo-950 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-primary-500 to-primary-700 rounded-2xl shadow-lg mb-4">
            <KeyRound className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            CONCIERGE
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-2">
            Enter your access code to continue
          </p>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <form onSubmit={handleSubmit}>
            <div className="mb-6">
              <label
                htmlFor="tag-input"
                className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2"
              >
                Access Code
              </label>
              <input
                id="tag-input"
                type="text"
                value={tagInput}
                onChange={(e) => {
                  setTagInput(e.target.value);
                  if (error) setError(null);
                }}
                placeholder="Enter your code..."
                className="w-full px-4 py-3 rounded-xl border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent transition-all text-lg tracking-wider"
                autoFocus
                autoComplete="off"
                disabled={loading}
              />
            </div>

            {error && (
              <div className="mb-4 p-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={loading || !tagInput.trim()}
              className="w-full flex items-center justify-center gap-2 px-6 py-3 bg-primary-600 hover:bg-primary-700 disabled:bg-gray-300 dark:disabled:bg-gray-600 text-white font-medium rounded-xl transition-all shadow-md hover:shadow-lg disabled:shadow-none"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Checking...
                </>
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  Continue
                </>
              )}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 dark:text-gray-500 mt-6">
          Your access code was provided by your administrator
        </p>
      </div>
    </div>
  );
};

export default ClientLoginPage;
