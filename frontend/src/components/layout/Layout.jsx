import { Outlet, Navigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useAuth } from '../../context/AuthContext';

const Layout = () => {
  const { isAuthenticated, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-cream">
        <p className="label-mono">Loading…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="flex min-h-screen bg-cream text-ink">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:z-[100] focus:top-2 focus:left-2
                   focus:px-4 focus:py-2 focus:bg-paper focus:text-ink focus:rounded-sm
                   focus:border-[1.5px] focus:border-iris focus:text-sm focus:font-medium"
      >
        Skip to content
      </a>
      <Sidebar />
      <div className="flex-1 flex flex-col w-full md:w-auto min-w-0">
        <Header />
        <main
          id="main-content"
          className="flex-1 px-4 py-6 md:px-8 md:py-8 pt-16 md:pt-8 overflow-x-hidden"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
