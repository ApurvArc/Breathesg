import { useCallback, useEffect, useState } from 'react';
import { BookOpen, Download, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../configs/api';
import { Card, EmptyState, QualitySeal, ScopeChip, StatCard, secondaryButtonClass } from '../components/ui';
import { formatDate, formatNumber } from '../utils/format';

const categoryLabels = {
  FUEL_COMBUSTION: 'Fuel Combustion',
  ELECTRICITY: 'Grid Electricity',
  BUSINESS_TRAVEL_AIR: 'Air Travel',
  BUSINESS_TRAVEL_HOTEL: 'Hotel',
  BUSINESS_TRAVEL_GROUND: 'Ground Transport',
  BUSINESS_TRAVEL_RAIL: 'Rail',
  PURCHASED_GOODS: 'Purchased Goods',
};

const cell = 'border-t border-outline-variant px-5 py-3 align-middle text-sm';
const headerCell = `${cell} bg-surface-container-highest text-left font-mono text-[11px] uppercase tracking-[0.05em] text-on-surface-variant`;

const LedgerPage = () => {
  const [entries, setEntries] = useState([]);
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null, page: 1, total_co2e: 0 });
  const [filters, setFilters] = useState({ scope: '', category: '' });
  const [loading, setLoading] = useState(true);
  const [availableCategories, setAvailableCategories] = useState([]);
  const [errorRate, setErrorRate] = useState(0);

  const fetchEntries = useCallback(async (page = 1) => {
    setLoading(true);
    const params = new URLSearchParams({ page });
    if (filters.scope) params.append('scope', filters.scope);
    if (filters.category) params.append('category', filters.category);

    try {
      const { data } = await api.get(`/ledger/?${params}`);
      setEntries(data.results || []);
      setPagination({ 
        count: data.count, 
        next: data.next, 
        previous: data.previous, 
        page,
        total_co2e: data.query_total_co2e || 0
      });
    } catch {
      toast.error('Failed to load ledger', { className: 'toast-error' });
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const id = window.setTimeout(() => fetchEntries(1), 0);
    return () => window.clearTimeout(id);
  }, [fetchEntries]);

  useEffect(() => {
    api.get('/dashboard/').then(({ data }) => {
      if (data?.data?.by_category) {
        setAvailableCategories(data.data.by_category.map((c) => c.category).filter(Boolean));
      }
      if (data?.data?.error_rate_percentage !== undefined) {
        setErrorRate(data.data.error_rate_percentage);
      }
    }).catch(() => {});
  }, []);

  const total = pagination.total_co2e || 0;
  const exportVisibleEntries = () => {
    if (!entries.length) {
      toast.error('No visible ledger entries to export', { className: 'toast-error' });
      return;
    }
    const columns = ['id', 'scope', 'category', 'start_date', 'end_date', 'facility', 'tco2e', 'approved_by'];
    const rows = entries.map((entry) => [
      entry.id,
      entry.scope,
      entry.category,
      entry.start_date,
      entry.end_date,
      entry.facility_name || '',
      entry.co2e_metric_tons,
      entry.approved_by_name || 'System',
    ]);
    const csv = [columns, ...rows].map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'carbon-ledger.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <>
      <div className="mb-8 grid grid-cols-[minmax(0,2fr)_minmax(280px,1fr)] gap-6 max-xl:grid-cols-1">
        <Card className="grid grid-cols-[1.5fr_0.7fr_0.7fr] items-center gap-6 max-md:grid-cols-1">
          <div>
            <span className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-outline">Ledger Status</span>
            <h2 className="mt-1.5 font-display text-2xl font-bold text-status-verified">Immutable & Auditable <i className="ml-1 inline-block h-2.5 w-2.5 rounded-full bg-status-verified" /></h2>
          </div>
          <div>
            <span className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-outline">Visible tCO2e</span>
            <strong className="mt-1.5 block font-display text-2xl font-extrabold text-on-surface">{formatNumber(total, 2)}</strong>
          </div>
          <div>
            <span className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-outline">Error Rate</span>
            <strong className="mt-1.5 block font-display text-2xl font-extrabold text-secondary">{errorRate.toFixed(2)}%</strong>
          </div>
        </Card>
        <Card tone="primary" className="relative min-h-32 overflow-hidden">
          <span className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-on-primary/75">Certification Status</span>
          <h2 className="mt-2 font-display text-2xl font-extrabold">Ready for Audit</h2>
          <ShieldCheck className="absolute -right-3 -bottom-4 opacity-15" size={100} />
        </Card>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_310px] items-start gap-6 max-xl:grid-cols-1">
        <Card className="overflow-hidden p-0">
          <div className="flex min-h-[72px] items-center justify-between gap-4 px-6 max-lg:flex-col max-lg:items-start max-lg:py-4">
            <h2 className="font-display text-xl font-bold text-primary m-0">Carbon Ledger Entries</h2>
            <div className="flex flex-wrap gap-2">
              <select className="h-9 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-sm text-on-surface outline-none focus:border-secondary" value={filters.scope} onChange={(event) => setFilters((f) => ({ ...f, scope: event.target.value }))}>
                <option value="">All Scopes</option>
                <option value="1">Scope 1</option>
                <option value="2">Scope 2</option>
                <option value="3">Scope 3</option>
              </select>
              <select className="h-9 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-sm text-on-surface outline-none focus:border-secondary" value={filters.category} onChange={(event) => setFilters((f) => ({ ...f, category: event.target.value }))}>
                <option value="">All Categories</option>
                {availableCategories.map((cat) => (
                  <option key={cat} value={cat}>{categoryLabels[cat] || 'Others'}</option>
                ))}
              </select>
              <button className={`${secondaryButtonClass} h-9 min-h-0 py-0`} onClick={exportVisibleEntries}><Download size={14} />Export</button>
            </div>
          </div>

          {loading ? (
            <div className="grid min-h-48 place-items-center"><div className="h-6 w-6 animate-spin rounded-full border-2 border-surface-variant border-t-primary" /></div>
          ) : entries.length === 0 ? (
            <EmptyState title="Ledger is empty" text="Approve records in the review queue to commit immutable entries." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr>
                    <th className={headerCell}>ID</th>
                    <th className={headerCell}>Scope</th>
                    <th className={headerCell}>Category</th>
                    <th className={headerCell}>Period</th>
                    <th className={headerCell}>Facility</th>
                    <th className={`${headerCell} text-right`}>Quantity</th>
                    <th className={`${headerCell} text-right`}>tCO2e</th>
                    <th className={headerCell}>EF Source</th>
                    <th className={headerCell}>Approved</th>
                  </tr>
                </thead>
                <tbody>
                  {entries.map((entry) => (
                    <tr key={entry.id} className="even:bg-surface-container/50 hover:bg-surface-container-low transition-colors">
                      <td className={`${cell} font-mono text-xs`}>#{entry.id.slice(0, 8)}</td>
                      <td className={cell}><ScopeChip scope={entry.scope} /></td>
                      <td className={cell}>{categoryLabels[entry.category] || 'Others'}</td>
                      <td className={`${cell} font-mono text-[11px]`}>{entry.start_date} to {entry.end_date}</td>
                      <td className={cell}>{entry.facility_name || '-'}</td>
                      <td className={`${cell} text-right font-mono tabular-nums text-xs`}>{formatNumber(entry.normalized_quantity, 2)} {entry.normalized_unit}</td>
                      <td className={`${cell} text-right font-mono tabular-nums text-xs font-bold text-on-surface`}>{formatNumber(Math.abs(entry.co2e_metric_tons), 6)}</td>
                      <td className={cell}>{entry.emission_factor_snapshot?.source || 'Snapshot'} {entry.emission_factor_snapshot?.publication_year || ''}</td>
                      <td className={cell}>{entry.approved_by_name || 'System'}<small className="mt-0.5 block text-on-surface-variant text-[10px]">{formatDate(entry.approved_at)}</small></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="flex items-center justify-end gap-3 border-t border-outline-variant px-6 py-3 max-sm:flex-wrap bg-surface-container-lowest">
            <span className="mr-auto text-xs text-on-surface-variant">Showing page {pagination.page} | {pagination.count} committed entries</span>
            <button className={`${secondaryButtonClass} h-8 min-h-0 py-0`} disabled={!pagination.previous} onClick={() => fetchEntries(pagination.page - 1)}>Previous</button>
            <button className={`${secondaryButtonClass} h-8 min-h-0 py-0`} disabled={!pagination.next} onClick={() => fetchEntries(pagination.page + 1)}>Next</button>
          </div>
        </Card>

        <aside className="grid gap-6">
          <StatCard label="Committed Entries" value={pagination.count} detail="Append-only rows" icon={BookOpen} />
          <Card className="text-center p-5">
            <QualitySeal value={(100 - errorRate).toFixed(1)} label="Data Quality" />
            <p className="mx-auto mt-5 max-w-60 text-sm leading-relaxed text-on-surface-variant">High precision normalization verified across submitted facilities and business travel records.</p>
          </Card>
        </aside>
      </div>
    </>
  );
};

export default LedgerPage;
