import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { AuthProvider, useAuth } from "@/lib/auth";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Signup from "@/pages/Signup";
import Dashboard from "@/pages/Dashboard";
import Leads from "@/pages/Leads";
import Analytics from "@/pages/Analytics";
import Settings from "@/pages/Settings";
import CaptureLead from "@/pages/CaptureLead";
import AppShell from "@/components/app/AppShell";

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen grid place-items-center text-slate-500">Loading…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" richColors />
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/capture/:ownerEmail" element={<CaptureLead />} />
            <Route path="/app" element={<Protected><Dashboard /></Protected>} />
            <Route path="/app/leads" element={<Protected><Leads /></Protected>} />
            <Route path="/app/analytics" element={<Protected><Analytics /></Protected>} />
            <Route path="/app/settings" element={<Protected><Settings /></Protected>} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </div>
  );
}
