import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './context/AuthContext';
import { BootstrapProvider } from './context/BootstrapContext';
import { ThemeProvider } from './context/ThemeContext';
import ErrorBoundary from './components/ErrorBoundary';
import Layout from './components/layout/Layout';
import ClientLayout from './components/layout/ClientLayout';
import BootstrapGate from './components/owner/BootstrapGate';
import OwnerLayout from './components/owner/OwnerLayout';
import RootRedirect from './components/owner/RootRedirect';

// Сторінки завантажуються лінево (React.lazy) — інакше всі 30+ сторінок
// потрапляють в один початковий бандл.

// Pages — legacy + client portal
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const TrainingPage = lazy(() => import('./pages/TrainingPage'));
const SandboxPage = lazy(() => import('./pages/SandboxPage'));
const HistoryPage = lazy(() => import('./pages/HistoryPage'));
const IntegrationsPage = lazy(() => import('./pages/IntegrationsPage'));
const ToolsPage = lazy(() => import('./pages/ToolsPage'));
const SkillsPage = lazy(() => import('./pages/SkillsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const LeadsPage = lazy(() => import('./pages/LeadsPage'));
const ClientLoginPage = lazy(() => import('./pages/ClientLoginPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const WebChatPage = lazy(() => import('./pages/WebChatPage'));

// Pages — owner admin
const SetupWizard = lazy(() => import('./pages/owner/SetupWizard'));
const OwnerLoginPage = lazy(() => import('./pages/owner/OwnerLoginPage'));
const OwnerDashboardPage = lazy(() => import('./pages/owner/OwnerDashboardPage'));
const OwnerSettingsPage = lazy(() => import('./pages/owner/OwnerSettingsPage'));
const LLMProvidersPage = lazy(() => import('./pages/owner/LLMProvidersPage'));
const LLMProviderEditPage = lazy(() => import('./pages/owner/LLMProviderEditPage'));
const EmbeddingModelsPage = lazy(() => import('./pages/owner/EmbeddingModelsPage'));
const EmbeddingModelEditPage = lazy(() => import('./pages/owner/EmbeddingModelEditPage'));
const ModelPairsPage = lazy(() => import('./pages/owner/ModelPairsPage'));
const ModelPairEditPage = lazy(() => import('./pages/owner/ModelPairEditPage'));
const PlatformDefaultsPage = lazy(() => import('./pages/owner/PlatformDefaultsPage'));
const MCPServersPage = lazy(() => import('./pages/owner/MCPServersPage'));
const MCPServerEditPage = lazy(() => import('./pages/owner/MCPServerEditPage'));
const ClientsPage = lazy(() => import('./pages/owner/ClientsPage'));
const ClientEditPage = lazy(() => import('./pages/owner/ClientEditPage'));
const BranchesPage = lazy(() => import('./pages/owner/BranchesPage'));
const BranchEditPage = lazy(() => import('./pages/owner/BranchEditPage'));
const SpecializationsPage = lazy(() => import('./pages/owner/SpecializationsPage'));
const SpecializationEditPage = lazy(() => import('./pages/owner/SpecializationEditPage'));
const FeatureFlagsPage = lazy(() => import('./pages/owner/FeatureFlagsPage'));
const FeatureFlagEditPage = lazy(() => import('./pages/owner/FeatureFlagEditPage'));
const SystemMessagesPage = lazy(() => import('./pages/owner/SystemMessagesPage'));
const SystemMessageEditPage = lazy(() => import('./pages/owner/SystemMessageEditPage'));

function PageFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600" />
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ThemeProvider>
          <BrowserRouter>
            <BootstrapProvider>
              <Suspense fallback={<PageFallback />}>
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
                    <Route path="specializations" element={<SpecializationsPage />} />
                    <Route path="specializations/new" element={<SpecializationEditPage />} />
                    <Route path="specializations/:id" element={<SpecializationEditPage />} />
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
                    <Route path="feature-flags" element={<FeatureFlagsPage />} />
                    <Route path="feature-flags/new" element={<FeatureFlagEditPage />} />
                    <Route path="feature-flags/:id" element={<FeatureFlagEditPage />} />
                    <Route path="system-messages" element={<SystemMessagesPage />} />
                    <Route path="system-messages/new" element={<SystemMessageEditPage />} />
                    <Route path="system-messages/:id" element={<SystemMessageEditPage />} />
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
                    <Route path="skills" element={<SkillsPage />} />
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
                    <Route path="/skills" element={<SkillsPage />} />
                    <Route path="/history" element={<HistoryPage />} />
                    <Route path="/settings" element={<SettingsPage />} />
                    <Route path="/leads" element={<LeadsPage />} />
                  </Route>

                  {/* Root redirect — bootstrap-aware */}
                  <Route path="/" element={<RootRedirect />} />
                </Routes>
              </Suspense>
            </BootstrapProvider>
          </BrowserRouter>
        </ThemeProvider>
      </AuthProvider>
    </ErrorBoundary>
  );
}

export default App;
