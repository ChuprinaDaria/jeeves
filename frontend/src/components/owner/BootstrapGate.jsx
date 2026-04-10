import { Navigate, useLocation } from 'react-router-dom';

import { useAuth } from '../../context/AuthContext';
import { useBootstrap } from '../../context/BootstrapContext';

const Spinner = () => (
  <div className="flex items-center justify-center min-h-screen bg-cream">
    <p className="label-mono">Loading…</p>
  </div>
);

const BootstrapGate = ({ children }) => {
  const { loading, setupRequired } = useBootstrap();
  const { user } = useAuth();
  const location = useLocation();

  if (loading) return <Spinner />;

  if (setupRequired) {
    return <Navigate to="/setup" replace state={{ from: location }} />;
  }

  const isOwner = user && user.role === 'owner';
  if (!isOwner) {
    return <Navigate to="/owner/login" replace state={{ from: location }} />;
  }

  return children;
};

export default BootstrapGate;
