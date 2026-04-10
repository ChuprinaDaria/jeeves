import { Outlet } from 'react-router-dom';

import GraceBanner from './GraceBanner';
import OwnerSidebar from './OwnerSidebar';
import ReadOnlyBanner from './ReadOnlyBanner';

const OwnerLayout = () => (
  <div className="flex min-h-screen bg-cream text-ink">
    <OwnerSidebar />
    <div className="flex-1 flex flex-col min-w-0">
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 overflow-x-hidden">
        <GraceBanner />
        <ReadOnlyBanner />
        <Outlet />
      </main>
    </div>
  </div>
);

export default OwnerLayout;
