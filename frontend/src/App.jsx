import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/layout/Layout';
import ClientLayout from './components/layout/ClientLayout';

// Pages
// import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import TrainingPage from './pages/TrainingPage';
import SandboxPage from './pages/SandboxPage';
import HistoryPage from './pages/HistoryPage';
import IntegrationsPage from './pages/IntegrationsPage';
import ToolsPage from './pages/ToolsPage';
import SettingsPage from './pages/SettingsPage';
import LeadsPage from './pages/LeadsPage';
import ClientLoginPage from './pages/ClientLoginPage';
import LoginPage from './pages/LoginPage';
import WebChatPage from './pages/WebChatPage';
// import PricingPage from './pages/PricingPage';

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <BrowserRouter>
        <Routes>
          {/* Client login page (enter tag) */}
          <Route path="/l" element={<ClientLoginPage />} />

          {/* New client portal with proper URLs: /l/:tag/dashboard etc. */}
          <Route path="/l/:tag" element={<ClientLayout />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="training" element={<TrainingPage />} />
            <Route path="sandbox" element={<SandboxPage />} />
            <Route path="integrations" element={<IntegrationsPage />} />
            <Route path="tools" element={<ToolsPage />} />
            <Route path="history" element={<HistoryPage />} />
            <Route path="settings" element={<SettingsPage />} />
            <Route path="leads" element={<LeadsPage />} />
          </Route>

          {/* Web Chat for B2C clients */}
          <Route path="/client" element={<WebChatPage />} />

          {/* Login page */}
          <Route path="/login" element={<LoginPage />} />

            <Route element={<Layout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/training" element={<TrainingPage />} />
              <Route path="/sandbox" element={<SandboxPage />} />
              <Route path="/integrations" element={<IntegrationsPage />} />
              <Route path="/tools" element={<ToolsPage />} />
              <Route path="/history" element={<HistoryPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/leads" element={<LeadsPage />} />
            </Route>

          {/* Redirect */}
          <Route path="/" element={<Navigate to="/l" replace />} />
        </Routes>
      </BrowserRouter>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
