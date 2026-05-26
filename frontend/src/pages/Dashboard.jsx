import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertTriangle, Building2, CheckCircle2, Database, Filter, Plane, PlugZap, ShieldCheck, Upload, UploadCloud, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../configs/api';
import { Card, EmptyState, ProgressRing, StatCard, StatusChip, secondaryButtonClass } from '../components/ui';
import { formatDate, formatNumber } from '../utils/format';

const sourceCardsMeta = [
  ['SAP', 'SAP ERP Central', 'Financial and operational footprint data cluster.', 'File Upload', Building2],
  ['UTILITY', 'Utility Portals', 'Direct energy provider bill uploads.', 'File Upload', Zap],
  ['TRAVEL', 'Corporate Travel', 'Navan and SAP Concur travel expenditure logs.', 'File Upload', Plane],
];

const Dashboard = () => {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activePeriod, setActivePeriod] = useState('All Time');
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.get(`/dashboard/?period=${encodeURIComponent(activePeriod)}`)
      .then(({ data }) => {
        if (active) setSummary(data.data);
      })
      .catch(() => toast.error('Failed to load dashboard', { className: 'toast-error' }))
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [activePeriod]);

  if (loading) {
    return <div className="grid min-h-[420px] place-items-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-outline-variant border-t-primary" /></div>;
  }

  const queue = summary?.review_queue || {};
  const total = summary?.total_co2e_metric_tons || 0;
  const recent = summary?.recent_batches || [];

  const totalBatches = summary?.total_batches || 0;
  const failedBatches = summary?.failed_batches || 0;
  const isSystemWarning = failedBatches > 0;

  const getSourceStatus = (type) => {
    const batches = recent.filter(b => b.source_type === type);
    if (!batches.length) return { status: 'Pending Data', sync: 'Never', warning: false };
    const latest = batches[0];
    const isError = latest.status === 'FAILED';
    return {
      status: isError ? 'Sync Failed' : 'Active Pipeline',
      sync: formatDate(latest.uploaded_at),
      warning: isError
    };
  };

  return (
    <>
      <div className="mb-6 flex flex-wrap gap-4 max-sm:gap-2">
        {['All Time', 'This Quarter', 'Last Quarter', 'YTD'].map((period) => (
          <button 
            key={period} 
            onClick={() => setActivePeriod(period)}
            className={`cursor-pointer rounded-full border px-4 py-1.5 font-label-mono text-[11px] font-bold tracking-[0.05em] transition ${activePeriod === period ? 'border-primary bg-primary-container text-on-primary-container shadow-sm' : 'border-outline-variant bg-surface text-on-surface-variant hover:border-primary/50 hover:text-primary'}`}
          >
            {period}
          </button>
        ))}
      </div>

      <div className="mb-8 grid grid-cols-4 gap-6 max-xl:grid-cols-2 max-sm:grid-cols-1">
        <StatCard label="Total Ingestions" value={formatNumber(totalBatches)} detail="Across 3 data sources" icon={UploadCloud} />
        <StatCard label="Review Queue" value={queue.pending || 0} detail="Rows pending validation" icon={AlertTriangle} tone="critical" />
        <StatCard label="Carbon Ledger" value={(Number(total)/1000).toFixed(1) + 'k'} detail="Verified tCO2e" icon={ShieldCheck} tone="verified" />
        <Card tone={isSystemWarning ? "critical" : "primary"} className="relative min-h-36 overflow-hidden">
          <span className={`font-label-mono text-[11px] font-bold uppercase tracking-[0.08em] ${isSystemWarning ? 'text-status-critical' : 'text-on-primary/75'}`}>System Status</span>
          <div className={`mt-4 font-display-lg text-4xl leading-none font-extrabold ${isSystemWarning ? 'text-status-critical' : 'text-on-primary'}`}>
            {isSystemWarning ? 'Degraded' : 'Stable'}
          </div>
          <div className={`mt-3 text-sm ${isSystemWarning ? 'text-on-surface-variant' : 'text-on-primary/85'}`}>
            {isSystemWarning ? `${failedBatches} failed parser jobs` : 'Parsers operational'}
          </div>
          {isSystemWarning ? (
            <AlertTriangle className="absolute -right-4 -bottom-4 opacity-15 text-status-critical" size={100} />
          ) : (
            <CheckCircle2 className="absolute -right-4 -bottom-4 opacity-15 text-on-primary" size={100} />
          )}
        </Card>
      </div>

      <section className="mb-10">
        <h2 className="mb-6 font-headline-sm text-[22px] font-bold text-on-surface flex items-center gap-2">
          Connected Enterprise Sources 
          <span className="font-body-md text-base font-normal text-on-surface-variant">(3 Active Clusters)</span>
        </h2>
        <div className="grid grid-cols-3 gap-6 max-xl:grid-cols-1">
          {sourceCardsMeta.map(([id, title, text, badge, Icon]) => {
            const { status, sync, warning } = getSourceStatus(id);
            return (
              <Card key={id} className={`flex min-h-60 flex-col group ${warning ? 'border-l-4 border-l-status-critical' : ''}`}>
                <div className="flex items-center justify-between gap-3">
                  <div className="grid h-12 w-12 place-items-center rounded-lg bg-surface-container text-primary transition-colors group-hover:bg-primary group-hover:text-on-primary"><Icon size={24} /></div>
                  <span className={`rounded px-2.5 py-1 font-label-mono text-[10px] uppercase tracking-[0.06em] ${warning ? 'bg-error-container text-status-critical' : 'bg-primary-fixed text-on-primary-fixed-variant'}`}>{badge}</span>
                </div>
                <h3 className="mb-1 mt-6 font-body-lg text-lg font-bold text-on-surface">{title}</h3>
                <p className="m-0 text-[15px] font-body-md leading-relaxed text-on-surface-variant mb-4">{text}</p>
                <div className="mt-auto flex items-center justify-between border-t border-outline-variant pt-4 font-label-mono text-xs text-on-surface-variant">
                  <span className={`flex items-center gap-1 ${warning ? "text-status-critical" : ""}`}>
                    <span className={`w-2 h-2 rounded-full ${warning ? "bg-status-critical" : "bg-status-verified"}`}></span>
                    {status}
                  </span>
                  <span className="text-outline">{sync}</span>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      <Card className="overflow-hidden p-0">
        <div className="flex min-h-[72px] items-center justify-between gap-4 px-6 border-b border-outline-variant py-4 max-md:flex-col max-md:items-start max-md:py-5">
          <h2 className="m-0 font-headline-sm text-[22px] font-bold text-on-surface">Recent Ingestion Batches</h2>
          <div className="flex gap-2">
            <button className={`${secondaryButtonClass} font-label-mono text-sm px-3 py-1.5 min-h-[auto] border-0 text-primary`} onClick={() => navigate('/review')}><Filter size={17} />View Queue</button>
            <button className={`${secondaryButtonClass} font-label-mono text-sm px-3 py-1.5 min-h-[auto] border-0 text-primary`} onClick={() => navigate('/ingest')}><Upload size={17} />Upload Data</button>
          </div>
        </div>
        {recent.length === 0 ? (
          <EmptyState title="No ingestion batches yet" text="Upload SAP, utility, or travel files to populate this overview." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-surface-container/50 text-left font-label-mono text-xs uppercase tracking-[0.05em] text-on-surface-variant">
                  <th className="border-b border-outline-variant px-6 py-3">Source Name</th>
                  <th className="border-b border-outline-variant px-6 py-3">Connection Type</th>
                  <th className="border-b border-outline-variant px-6 py-3">Batch ID</th>
                  <th className="border-b border-outline-variant px-6 py-3">Last Sync Date</th>
                  <th className="border-b border-outline-variant px-6 py-3 text-right">Status Badge</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {recent.map((batch) => (
                  <tr key={batch.id} className="transition audit-row-hover even:bg-tertiary-fixed/10 cursor-pointer" onClick={() => navigate(`/review?batch_id=${batch.id}`)}>
                    <td className="px-6 py-4 font-data-tabular text-data-tabular text-on-surface">{batch.original_filename}</td>
                    <td className="px-6 py-4 font-label-mono text-xs">File Upload</td>
                    <td className="px-6 py-4 font-data-tabular text-data-tabular text-on-surface-variant">#{batch.id.slice(0, 8)}</td>
                    <td className="px-6 py-4 font-data-tabular text-data-tabular text-on-surface">{formatDate(batch.uploaded_at)}</td>
                    <td className="px-6 py-4 text-right"><StatusChip status={batch.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="border-t border-outline-variant px-6 py-4 text-xs font-label-mono text-on-surface-variant flex justify-between items-center bg-surface-container/20">
          <span>Approved inventory total: {Number(total).toFixed(3)} tCO2e</span>
        </div>
      </Card>
    </>
  );
};

export default Dashboard;
