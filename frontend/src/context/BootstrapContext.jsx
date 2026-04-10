import { createContext, useCallback, useContext, useEffect, useState } from 'react';

import { platformAPI } from '../api/owner';

const BootstrapContext = createContext(null);

export const useBootstrap = () => {
  const ctx = useContext(BootstrapContext);
  if (!ctx) throw new Error('useBootstrap must be used inside BootstrapProvider');
  return ctx;
};

export const BootstrapProvider = ({ children }) => {
  const [state, setState] = useState({
    loading: true,
    setupRequired: null,
    licenseStatus: null,
    licenseLastVerifiedAt: null,
    graceDaysRemaining: null,
    error: null,
  });

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const { data } = await platformAPI.getBootstrap();
      setState({
        loading: false,
        setupRequired: data.setup_required,
        licenseStatus: data.license_status,
        licenseLastVerifiedAt: data.license_last_verified_at,
        graceDaysRemaining: data.grace_days_remaining,
        error: null,
      });
    } catch (err) {
      setState((s) => ({
        ...s,
        loading: false,
        error: err?.message || 'bootstrap_failed',
      }));
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const value = {
    ...state,
    refresh: load,
  };

  return (
    <BootstrapContext.Provider value={value}>
      {children}
    </BootstrapContext.Provider>
  );
};
