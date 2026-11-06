import { Suspense, lazy, useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import { api } from "./services/api";
import type { User } from "./types";
import { Loading } from "./components/Shared";

const LoginPage = lazy(() => import("./pages/LoginPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const RequisitionsPage = lazy(() => import("./pages/RequisitionsPage"));
const CandidatesPage = lazy(() => import("./pages/CandidatesPage"));
const CandidateProfilePage = lazy(() => import("./pages/CandidateProfilePage"));
const ClientPage = lazy(() => import("./pages/ClientPage"));
const PipelinePage = lazy(() => import("./pages/PipelinePage"));

function Protected({ user, children, role }: { user: User | null; children: React.ReactNode; role?: User["role"] }) {
  if (!user) return <Navigate to="/login" replace />;
  if (role && user.role !== role) return <Navigate to={user.role === "client" ? "/client" : "/dashboard"} replace />;
  return children;
}

export default function App() {
  const [user, setUser] = useState<User | null>(() => {
    try { return JSON.parse(localStorage.getItem("hirerank_user") || "null") as User | null; } catch { return null; }
  });
  const navigate = useNavigate();

  useEffect(() => {
    const token = localStorage.getItem("hirerank_token");
    if (!token) return;
    api<User>("/api/auth/me").then(validUser => {
      setUser(validUser);
      localStorage.setItem("hirerank_user", JSON.stringify(validUser));
    }).catch(() => {
      localStorage.removeItem("hirerank_token");
      localStorage.removeItem("hirerank_user");
      setUser(null);
    });
  }, []);

  const onLogin = (nextUser: User) => {
    setUser(nextUser);
    localStorage.setItem("hirerank_user", JSON.stringify(nextUser));
    navigate(nextUser.role === "client" ? "/client" : "/dashboard", { replace: true });
  };
  const home = user?.role === "client" ? "/client" : "/dashboard";
  return <Routes>
    <Route path="/login" element={user ? <Navigate to={home} replace /> : <Suspense fallback={<Loading />}><LoginPage onLogin={onLogin} /></Suspense>} />
    <Route path="/" element={<Navigate to={home} replace />} />
    <Route path="/" element={<Protected user={user}><AppLayout user={user!} /></Protected>}>
      <Route path="dashboard" element={<Protected user={user} role="recruiter"><Suspense fallback={<Loading />}><DashboardPage /></Suspense></Protected>} />
      <Route path="requisitions" element={<Protected user={user} role="recruiter"><Suspense fallback={<Loading />}><RequisitionsPage /></Suspense></Protected>} />
      <Route path="candidates" element={<Protected user={user} role="recruiter"><Suspense fallback={<Loading />}><CandidatesPage /></Suspense></Protected>} />
      <Route path="candidates/:candidateId" element={<Protected user={user}><Suspense fallback={<Loading />}><CandidateProfilePage user={user!} /></Suspense></Protected>} />
      <Route path="client" element={<Protected user={user} role="client"><Suspense fallback={<Loading />}><ClientPage /></Suspense></Protected>} />
      <Route path="pipeline" element={<Protected user={user} role="recruiter"><Suspense fallback={<Loading />}><PipelinePage /></Suspense></Protected>} />
    </Route>
    <Route path="*" element={<Navigate to={home} replace />} />
  </Routes>;
}
