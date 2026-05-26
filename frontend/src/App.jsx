import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { useEffect, useState } from 'react';
import { AppProvider } from './context/AppContext';
import { useAppContext } from './context/AuthContext';
import AppShell from './components/AppShell';
import AuditPage from './pages/AuditPage';
import Dashboard from './pages/Dashboard';
import IngestPage from './pages/IngestPage';
import LedgerPage from './pages/LedgerPage';
import Login from './pages/Login';
import ReviewPage from './pages/ReviewPage';
import SettingsPage from './pages/SettingsPage';
import Signup from './pages/Signup';
import api from './configs/api';
import ErrorBoundary from './components/ErrorBoundary';

const ProtectedLayout = ({ children }) => {
  const { user, loading } = useAppContext();
  const location = useLocation();
  const [reviewCount, setReviewCount] = useState(0);

  useEffect(() => {
    let active = true;
    if (!user) return undefined;
    api.get('/dashboard/')
      .then(({ data }) => {
        const queue = data.data?.review_queue || {};
        if (active) setReviewCount((queue.pending || 0) + (queue.flagged || 0));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [user, location.pathname]);

  if (loading) {
    return (
      <div className="grid min-h-screen place-items-center bg-[#f9faf2]">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-[#e2e3dc] border-t-[#154212]" />
      </div>
    );
  }

  if (!user) return <Navigate to="/login" replace />;

  return (
    <AppShell path={location.pathname} reviewCount={reviewCount}>
      {children}
    </AppShell>
  );
};

const AppRoutes = () => (
  <Routes>
    <Route path="/login" element={<Login />} />
    <Route path="/signup" element={<Signup />} />
    <Route path="/" element={<Navigate to="/dashboard" replace />} />
    <Route path="/dashboard" element={<ProtectedLayout><Dashboard /></ProtectedLayout>} />
    <Route path="/ingest" element={<ProtectedLayout><IngestPage /></ProtectedLayout>} />
    <Route path="/review" element={<ProtectedLayout><ReviewPage /></ProtectedLayout>} />
    <Route path="/ledger" element={<ProtectedLayout><LedgerPage /></ProtectedLayout>} />
    <Route path="/audit" element={<ProtectedLayout><AuditPage /></ProtectedLayout>} />
    <Route path="/settings" element={<ProtectedLayout><SettingsPage /></ProtectedLayout>} />
  </Routes>
);

const App = () => (
  <AppProvider>
    <BrowserRouter>
      <ErrorBoundary>
        <Toaster position="top-right" toastOptions={{ duration: 3600 }} />
        <AppRoutes />
      </ErrorBoundary>
    </BrowserRouter>
  </AppProvider>
);

export default App;
