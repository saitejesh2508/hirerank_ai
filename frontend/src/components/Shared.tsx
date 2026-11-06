import { LoaderCircle, Search, Sparkles } from "lucide-react";
import type { ReactNode } from "react";

export function PageTitle({ eyebrow, title, description, action }: { eyebrow?: string; title: string; description?: string; action?: ReactNode }) {
  return <div className="page-title"><div>{eyebrow && <div className="eyebrow">{eyebrow}</div>}<h1>{title}</h1>{description && <p>{description}</p>}</div>{action}</div>;
}

export function Button({ children, variant = "primary", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger" }) {
  return <button className={`button button-${variant} ${props.className || ""}`} {...props}>{children}</button>;
}

export function Loading() {
  return <div className="loading"><LoaderCircle className="spin" size={18} /> Loading workspace…</div>;
}

export function ErrorState({ error, onRetry }: { error: string; onRetry?: () => void }) {
  return <div className="notice notice-error"><span>{error}</span>{onRetry && <button className="text-button" onClick={onRetry}>Try again</button>}</div>;
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return <div className="empty-state"><div className="empty-icon"><Search size={20} /></div><h3>{title}</h3><p>{message}</p>{action}</div>;
}

export function SyntheticTag() {
  return <span className="synthetic-tag"><Sparkles size={12} /> Synthetic demo data</span>;
}

export function ScoreBadge({ score, category }: { score?: number; category?: string }) {
  const className = score === undefined ? "score-muted" : score >= 85 ? "score-strong" : score >= 70 ? "score-good" : score >= 50 ? "score-partial" : "score-low";
  return <span className={`score-badge ${className}`}><strong>{score === undefined ? "—" : `${Math.round(score)}%`}</strong>{category && <small>{category}</small>}</span>;
}
