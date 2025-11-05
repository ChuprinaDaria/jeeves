import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useAuth } from '../../context/AuthContext';

const Layout = () => {
  const { user } = useAuth();

  return (
    <div className="flex min-h-screen bg-gray-50">
      <Sidebar />
      <div className="flex-1 flex flex-col w-full md:w-auto">
        {user?.subscription_status === 'trial' && <TrialBanner />}
        <Header />
        {/* Mobile-optimized padding: smaller on mobile (p-3), larger on desktop (md:p-6) */}
        {/* Extra top padding on mobile (pt-16) to account for hamburger menu button */}
        <main className="flex-1 p-3 md:p-6 pt-16 md:pt-6 overflow-x-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
