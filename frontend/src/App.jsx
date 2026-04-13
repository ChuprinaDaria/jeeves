import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { BootstrapProvider } from './context/BootstrapContext';
import { ThemeProvider } from './context/ThemeContext';
import Layout from './components/layout/Layout';
import ClientLayout from './components/layout/ClientLayout';
import BootstrapGate from './components/owner/BootstrapGate';
import OwnerLayout from './components/owner/OwnerLayout';
import RootRedirect from './components/owner/RootRedirect';

// Pages — legacy + client portal
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

// Pages — owner admin
import SetupWizard from './pages/owner/SetupWizard';
import OwnerLoginPage from './pages/owner/OwnerLoginPage';
import OwnerDashboardPage from './pages/owner/OwnerDashboardPage';
import OwnerSettingsPage from './pages/owner/OwnerSettingsPage';
import StubPage from './pages/owner/StubPage';
import LLMProvidersPage from './pages/owner/LLMProvidersPage';
import LLMProviderEditPage from './pages/owner/LLMProviderEditPage';
import EmbeddingModelsPage from './pages/owner/EmbeddingModelsPage';
import EmbeddingModelEditPage from './pages/owner/EmbeddingModelEditPage';
import ModelPairsPage from './pages/owner/ModelPairsPage';
import ModelPairEditPage from './pages/owner/ModelPairEditPage';
import PlatformDefaultsPage from './pages/owner/PlatformDefaultsPage';
import MCPServersPage from './pages/owner/MCPServersPage';
import MCPServerEditPage from './pages/owner/MCPServerEditPage';
import ClientsPage from './pages/owner/ClientsPage';
import ClientEditPage from './pages/owner/ClientEditPage';
import BranchesPage from './pages/owner/BranchesPage';
import BranchEditPage from './pages/owner/BranchEditPage';

function App() {
  return (
    <AuthProvider>
      <ThemeProvider>
        <BrowserRouter>
          <BootstrapProvider>
            <Routes>
              {/* === OWNER ADMIN — public === */}
              <Route path="/setup" element={<SetupWizard />} />
              <Route path="/owner/login" element={<OwnerLoginPage />} />

              {/* === OWNER ADMIN — protected === */}
              <Route
                path="/owner"
                element={
                  <BootstrapGate>
                    <OwnerLayout />
                  </BootstrapGate>
                }
              >
                <Route index element={<Navigate to="dashboard" replace />} />
                <Route path="dashboard" element={<OwnerDashboardPage />} />
                <Route path="branches" element={<BranchesPage />} />
                <Route path="branches/new" element={<BranchEditPage />} />
                <Route path="branches/:id" element={<BranchEditPage />} />
                <Route path="specializations" element={<StubPage title="Specializations" />} />
                <Route path="clients" element={<ClientsPage />} />
                <Route path="clients/new" element={<ClientEditPage />} />
                <Route path="clients/:id" element={<ClientEditPage />} />
                <Route path="mcp-servers" element={<MCPServersPage />} />
                <Route path="mcp-servers/new" element={<MCPServerEditPage />} />
                <Route path="mcp-servers/:id" element={<MCPServerEditPage />} />
                <Route path="ai-providers" element={<Navigate to="llm" replace />} />
                <Route path="ai-providers/llm" element={<LLMProvidersPage />} />
                <Route path="ai-providers/llm/new" element={<LLMProviderEditPage />} />
                <Route path="ai-providers/llm/:id" element={<LLMProviderEditPage />} />
                <Route path="ai-providers/embeddings" element={<EmbeddingModelsPage />} />
                <Route path="ai-providers/embeddings/new" element={<EmbeddingModelEditPage />} />
                <Route path="ai-providers/embeddings/:id" element={<EmbeddingModelEditPage />} />
                <Route path="ai-providers/pairs" element={<ModelPairsPage />} />
                <Route path="ai-providers/pairs/new" element={<ModelPairEditPage />} />
                <Route path="ai-providers/pairs/:id" element={<ModelPairEditPage />} />
                <Route path="settings/defaults" element={<PlatformDefaultsPage />} />
                <Route path="settings" element={<OwnerSettingsPage />} />
              </Route>

              {/* === CLIENT PORTAL (existing, untouched) === */}
              <Route path="/l" element={<ClientLoginPage />} />
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

              {/* Legacy login + Layout block, kept untouched */}
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

              {/* Root redirect — bootstrap-aware */}
              <Route path="/" element={<RootRedirect />} />
            </Routes>
          </BootstrapProvider>
        </BrowserRouter>
      </ThemeProvider>
    </AuthProvider>
  );
}

export default App;
