import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  Clock3,
  FileText,
  Info,
  Search,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

export const cardClass = 'rounded-xl border border-outline-variant bg-surface-container-lowest p-5 transition hover:shadow-[0_4px_20px_rgba(45,90,39,0.08)]';
export const primaryButtonClass = 'inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg border border-transparent bg-primary px-4 text-sm font-bold text-on-primary no-underline transition hover:-translate-y-0.5 hover:shadow-[0_4px_20px_rgba(45,90,39,0.08)] disabled:cursor-not-allowed disabled:opacity-50';
export const secondaryButtonClass = 'inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg border border-outline-variant bg-transparent px-4 text-sm font-bold text-primary no-underline transition hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50';
export const ghostButtonClass = 'inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg border border-transparent bg-transparent px-4 text-sm font-bold text-on-surface-variant transition hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50';
export const dangerButtonClass = 'inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg border border-status-critical bg-surface-container-lowest px-4 text-sm font-bold text-status-critical transition hover:bg-error-container disabled:cursor-not-allowed disabled:opacity-50';
export const labelClass = 'font-label-mono text-[11px] font-bold uppercase tracking-[0.08em] text-outline';
export const inputClass = 'min-h-10 w-full rounded-lg border border-outline bg-surface-container-lowest px-3 py-2 text-sm text-on-surface outline-none focus:border-secondary focus:ring-4 focus:ring-secondary/15';

export const Card = ({ children, className = '', tone = '' }) => (
  <div className={`${tone === 'primary' ? 'rounded-xl border border-primary-container bg-primary-container p-5 text-on-primary' : cardClass} ${className}`}>
    {children}
  </div>
);

export const StatCard = ({ label, value, detail, icon: Icon = Info, tone = 'primary' }) => {
  const colors = {
    primary: 'text-primary',
    blue: 'text-audit-blue',
    critical: 'text-status-critical',
    secondary: 'text-secondary',
  };
  const isInverse = tone === 'inverse';

  return (
    <Card className="min-h-36" tone={isInverse ? 'primary' : ''}>
      <div className={`mb-5 flex items-center justify-between ${isInverse ? 'text-on-primary/75' : 'text-outline'}`}>
        <span className={`font-label-mono text-[11px] font-bold uppercase tracking-[0.08em] ${isInverse ? 'text-on-primary/85' : 'text-outline'}`}>{label}</span>
        <Icon size={18} />
      </div>
      <div className={`font-display-lg text-4xl leading-none font-extrabold ${isInverse ? 'text-on-primary' : colors[tone] || colors.primary}`}>{value}</div>
      {detail && <div className={`mt-3 text-sm ${isInverse ? 'text-on-primary/85' : 'text-on-surface-variant'}`}>{detail}</div>}
    </Card>
  );
};

export const EmptyState = ({ title = 'No data yet', text = 'Upload or approve records to populate this view.' }) => (
  <div className="grid min-h-48 place-items-center content-center gap-2 text-center text-outline">
    <FileText size={28} />
    <strong className="text-on-surface font-headline-sm text-base">{title}</strong>
    <span className="text-sm">{text}</span>
  </div>
);

export const SearchBox = ({ value, onChange, placeholder = 'Search...' }) => (
  <label className="flex h-10 items-center gap-2 rounded-full border border-outline-variant bg-surface-container-low px-3 text-outline">
    <Search size={16} />
    <input className="w-48 border-0 bg-transparent text-sm text-on-surface outline-none" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
  </label>
);

export const StatusChip = ({ status }) => {
  const normalized = (status || '').toUpperCase();
  const map = {
    PENDING: ['Pending', Clock3, 'bg-[#fff0bf] text-[#8a5300]'],
    FLAGGED: ['Flagged', AlertTriangle, 'bg-error-container text-status-critical'],
    APPROVED: ['Approved', CheckCircle2, 'bg-[#e6efe4] text-status-verified'],
    REJECTED: ['Rejected', XCircle, 'bg-surface-container text-on-surface-variant'],
    DONE: ['Success', CheckCircle2, 'bg-[#e6efe4] text-status-verified'],
    FAILED: ['Failed', XCircle, 'bg-error-container text-status-critical'],
    PROCESSING: ['Processing', Clock3, 'bg-[#e6edf7] text-audit-blue'],
    DUPLICATE: ['Duplicate', CircleHelp, 'bg-[#fff0bf] text-[#8a5300]'],
  };
  const [label, Icon, classes] = map[normalized] || [status || 'Unknown', CircleHelp, 'bg-surface-container text-on-surface-variant'];
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 font-label-mono text-[10px] font-bold tracking-[0.05em] ${classes}`}>
      <Icon size={11} />
      {label}
    </span>
  );
};

export const AuditActionChip = ({ action, label }) => {
  const normalized = (action || '').toUpperCase();
  const map = {
    INGEST: ['Ingested', 'bg-[#e6edf7] text-audit-blue'],
    APPROVE: ['Approved', 'bg-[#e6efe4] text-status-verified'],
    REJECT: ['Rejected', 'bg-surface-container text-on-surface-variant'],
    FLAG: ['Flagged', 'bg-error-container text-status-critical'],
    EDIT: ['Edited', 'bg-[#fff0bf] text-[#8a5300]'],
    LOCK: ['Locked', 'bg-[#e6efe4] text-status-verified'],
    REVERSE: ['Reversed', 'bg-error-container text-status-critical'],
  };
  const [fallbackLabel, classes] = map[normalized] || [normalized || 'Event', 'bg-surface-container text-on-surface-variant'];
  return (
    <span className={`inline-flex rounded-full px-3 py-1.5 font-label-mono text-xs font-bold tracking-[0.05em] ${classes}`}>
      {label || fallbackLabel}
    </span>
  );
};

export const ScopeChip = ({ scope }) => {
  const classes = {
    1: 'bg-error-container text-status-critical',
    2: 'bg-[#fff0bf] text-[#7c4d00]',
    3: 'bg-secondary-container text-secondary',
  };
  return <span className={`inline-flex rounded-full px-2.5 py-1 font-label-mono text-[10px] font-bold tracking-[0.05em] ${classes[scope] || classes[3]}`}>Scope {scope || '3'}</span>;
};

export const ProgressRing = ({ value = 75, label = 'Capacity', size = 150 }) => {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (Math.min(value, 100) / 100) * circumference;

  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg className="h-full w-full -rotate-90" viewBox="0 0 140 140">
        <circle className="fill-none stroke-white/25 [stroke-linecap:round] [stroke-width:12]" cx="70" cy="70" r={radius} />
        <circle className="fill-none stroke-white transition-all [stroke-linecap:round] [stroke-width:12]" cx="70" cy="70" r={radius} strokeDasharray={circumference} strokeDashoffset={offset} />
      </svg>
      <div className="absolute inset-0 grid place-items-center content-center text-on-primary">
        <strong className="font-display-lg text-xl font-extrabold">{value}%</strong>
        <span className="mt-1 font-label-mono text-[9px] font-bold uppercase tracking-[0.12em]">{label}</span>
      </div>
    </div>
  );
};

export const QualitySeal = ({ value = '99.8', label = 'Data Quality' }) => (
  <div className="mx-auto grid h-44 w-44 place-items-center content-center gap-1 rounded-full border-4 border-primary text-primary">
    <ShieldCheck size={24} />
    <span className="font-label-mono text-[10px] font-bold uppercase text-on-surface-variant">{label}</span>
    <strong className="font-display-lg text-4xl leading-none font-extrabold">{value}</strong>
    <small className="text-secondary text-xs">Index</small>
  </div>
);
