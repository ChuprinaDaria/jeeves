import { Link } from 'react-router-dom';

import { useBootstrap } from '../../context/BootstrapContext';

const GraceBanner = () => {
  const { licenseStatus, graceDaysRemaining } = useBootstrap();
  if (licenseStatus !== 'grace') return null;

  const days = graceDaysRemaining ?? 0;
  return (
    <div className="bg-yellow-100 border-l-4 border-yellow-500 text-yellow-900 px-4 py-3 mb-4">
      <p className="text-sm">
        License validation failed — we'll retry automatically.{' '}
        <strong>{days} day{days === 1 ? '' : 's'} remaining</strong> before the
        platform enters read-only mode.{' '}
        <Link to="/owner/settings" className="underline font-medium">
          Re-verify now →
        </Link>
      </p>
    </div>
  );
};

export default GraceBanner;
