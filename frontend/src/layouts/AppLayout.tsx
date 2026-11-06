import { Activity, BriefcaseBusiness, Building2, ChevronDown, ClipboardList, LayoutDashboard, LogOut, Users, X } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useState } from "react";
import type { User } from "../types";

const recruiterLinks = [
  { to: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { to: "/requisitions", label: "Requisitions", icon: BriefcaseBusiness },
  { to: "/candidates", label: "Candidates", icon: Users },
  { to: "/pipeline", label: "Pipeline", icon: Activity },
];

export default function AppLayout({ user }: { user: User }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const signOut = () => {
    localStorage.removeItem("hirerank_token");
    localStorage.removeItem("hirerank_user");
    navigate("/login");
  };
  const links = user.role === "client" ? [{ to: "/client", label: "Client review", icon: Building2 }] : recruiterLinks;
  return <div className="app-shell">
    <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
      <div className="brand"><div className="brand-mark">H</div><span>hirerank<span className="brand-ai">.ai</span></span><button className="mobile-close" onClick={() => setOpen(false)} aria-label="Close menu"><X size={18} /></button></div>
      <div className="workspace-switch"><div className="workspace-icon"><Building2 size={16} /></div><div><strong>{user.role === "client" ? "Client workspace" : "Talent operations"}</strong><small>{user.role === "client" ? "Hiring team" : "Recruiting team"}</small></div><ChevronDown size={14} /></div>
      <div className="nav-caption">WORKSPACE</div>
      <nav className="nav-list">{links.map(({ to, label, icon: Icon }) => <NavLink key={to} to={to} onClick={() => setOpen(false)} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}><Icon size={17} /><span>{label}</span>{label === "Candidates" && <span className="nav-dot" />}</NavLink>)}</nav>
      <div className="sidebar-bottom"><div className="help-card"><div className="help-icon"><ClipboardList size={16} /></div><strong>Hiring, with clarity.</strong><p>Fair, evidence-backed decisions at every step.</p></div><button className="profile-menu" onClick={signOut}><div className="avatar">{user.full_name.split(" ").map(part => part[0]).slice(0, 2).join("")}</div><div className="profile-text"><strong>{user.full_name}</strong><small>{user.role === "client" ? "Hiring manager" : "Recruiter"}</small></div><LogOut size={16} /></button></div>
    </aside>
    {open && <button className="sidebar-scrim" onClick={() => setOpen(false)} aria-label="Close navigation" />}
    <main className="main-shell"><header className="topbar"><button className="menu-toggle" onClick={() => setOpen(true)} aria-label="Open menu"><span /></button><div className="breadcrumbs">Workspace <span>/</span> <strong>{user.role === "client" ? "Client review" : "Recruiting"}</strong></div><div className="topbar-right"><span className="status-indicator" /> All systems operational <div className="top-avatar">{user.full_name[0]}</div></div></header><div className="page-content"><Outlet /></div></main>
  </div>;
}
