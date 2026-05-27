import { Outlet } from 'react-router-dom';

import OwnerSidebar from './OwnerSidebar';

const OwnerLayout = () => (
  <div className="flex min-h-screen bg-cream text-ink">
    <OwnerSidebar />
    <div className="flex-1 flex flex-col min-w-0">
      <main className="flex-1 px-4 py-6 md:px-8 md:py-8 overflow-x-hidden">
        <Outlet />
      </main>
      <footer className="px-4 py-3 text-center text-xs text-ink/40">
        Jeeves — by Daria Chuprina &amp; open-source community. Forever free.
      </footer>
    </div>
  </div>
);

export default OwnerLayout;
