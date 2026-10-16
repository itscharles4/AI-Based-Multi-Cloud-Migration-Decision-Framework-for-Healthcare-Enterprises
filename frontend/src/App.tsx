// src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';

import Layout      from './components/Layout';
import SignIn      from './pages/SignIn';
import Overview    from './pages/Overview';
import LiveMonitor from './pages/LiveMonitor';
import Devices     from './pages/Devices';
import Alerts      from './pages/Alerts';
import DecisionLab from './pages/DecisionLab';
import SystemInfo  from './pages/SystemInfo';
import Placeholder from './pages/Placeholder';

const qc = new QueryClient({
  defaultOptions: { queries: { retry: 2, staleTime: 5_000 } },
});

/** Redirect to /login if not authenticated */
function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (!user) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

/** Redirect to / if already logged in */
function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  if (user) return <Navigate to="/" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={
        <PublicOnly><SignIn /></PublicOnly>
      } />

      {/* Protected — inside the Layout shell */}
      <Route element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Overview />} />
        <Route path="monitor"    element={<LiveMonitor />} />
        <Route path="devices"    element={<Devices />} />
        <Route path="alerts"     element={<Alerts />} />
        <Route path="decisionlab" element={<DecisionLab />} />
        <Route path="model"      element={<Placeholder title="Model & Data" desc="Model version, MAE/RMSE vs baseline, predicted vs actual chart — Phase F4." />} />
        <Route path="audit"      element={<Placeholder title="Audit" desc="Hash-chained log with Verify chain button — Track B Phase F4." />} />
        <Route path="system"     element={<SystemInfo />} />
        <Route path="admin"      element={<Placeholder title="Admin" desc="Users, thresholds, simulator console — Track B Phase F4." />} />
      </Route>

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
