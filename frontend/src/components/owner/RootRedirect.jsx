import { Navigate } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const RootRedirect = () => {
  const { loading, setupRequired } = useBootstrap();
  const { user } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-cream">
        <p className="label-mono">Loading…</p>
      </div>
    );
  }

  if (setupRequired) return <Navigate to="/setup" replace />;
  if (user && user.role === 'owner') return <Navigate to="/owner/dashboard" replace />;
  return <Navigate to="/owner/login" replace />;
};

export default RootRedirect;
