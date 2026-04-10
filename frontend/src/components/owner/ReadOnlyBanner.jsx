import { Link } from 'react-router-dom';

import { useBootstrap } from '../../context/BootstrapContext';

const ReadOnlyBanner = () => {
  const { licenseStatus } = useBootstrap();
  if (licenseStatus !== 'expired') return null;

  return (
    <div className="bg-red-100 border-l-4 border-red-500 text-red-900 px-4 py-3 mb-4">
      <p className="text-sm">
        <strong>License expired.</strong> Platform is in read-only mode.{' '}
        <Link to="/owner/settings" className="underline font-medium">
          Update your license →
        </Link>
      </p>
    </div>
  );
};

export default ReadOnlyBanner;
