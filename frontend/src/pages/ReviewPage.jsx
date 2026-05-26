import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { CheckCircle2, Download, Eye, Flag, ListChecks, ShieldCheck, TriangleAlert, X, XCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../configs/api';
import {
  Card,
  EmptyState,
  ScopeChip,
  SearchBox,
  StatCard,
  StatusChip,
  dangerButtonClass,
  inputClass,
  labelClass,
  primaryButtonClass,
  secondaryButtonClass,
} from '../components/ui';
import { formatNumber } from '../utils/format';

const categoryLabels = {
  FUEL_COMBUSTION: 'Fuel Combustion',
  ELECTRICITY: 'Grid Electricity',
  BUSINESS_TRAVEL_AIR: 'Air Travel',
  BUSINESS_TRAVEL_HOTEL: 'Hotel',
  BUSINESS_TRAVEL_GROUND: 'Ground Transport',
  BUSINESS_TRAVEL_RAIL: 'Rail',
  PURCHASED_GOODS: 'Purchased Goods',
};

const cell = 'border-t border-outline-variant px-6 py-4 align-middle';
const headerCell = `${cell} bg-surface-container-highest text-left font-label-mono text-xs uppercase tracking-[0.05em] text-on-surface-variant`;

const RecordDrawer = ({ record, onClose, onRefresh }) => {
  const [note, setNote] = useState('');
  const [editQty, setEditQty] = useState('');
  const [editUnit, setEditUnit] = useState('');
  const [loading, setLoading] = useState(false);

  const submit = async (status) => {
    setLoading(true);
    const payload = { status, review_note: note };
    if (editQty) {
      payload.normalized_quantity = editQty;
      payload.normalized_unit = editUnit || record.normalized_unit;
      payload.edit_note = note || 'Analyst correction';
    }

    try {
      await api.patch(`/records/${record.id}/`, payload);
      toast.success(status === 'APPROVED' ? 'Approved for audit' : `Record marked ${status.toLowerCase()}`, { className: 'toast-success' });
      onRefresh();
      onClose();
    } catch (error) {
      toast.error(error.response?.data?.message || 'Review action failed', { className: 'toast-error' });
    } finally {
      setLoading(false);
    }
  };

  const readonly = ['APPROVED', 'REJECTED'].includes(record.status);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-on-surface/30 backdrop-blur-sm" onClick={onClose}>
      <aside className="h-screen w-full max-w-[560px] overflow-auto border-l border-outline-variant bg-surface-container-lowest p-7 shadow-[-20px_0_60px_rgba(25,28,24,0.12)]" onClick={(event) => event.stopPropagation()}>
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex gap-2"><StatusChip status={record.status} /><ScopeChip scope={record.scope} /></div>
            <h2 className="mb-1 mt-4 font-display-lg text-3xl font-extrabold text-primary">Row #{record.row_number}</h2>
            <span className="text-on-surface-variant">{record.ingestion_log_filename}</span>
          </div>
          <button className="grid h-10 w-10 place-items-center rounded-full border-0 bg-transparent hover:bg-surface-container" onClick={onClose}><X size={20} /></button>
        </div>

        <div className="grid justify-items-center gap-2 rounded-xl border border-outline-variant bg-surface-container-low p-6 text-center">
          <span className="text-on-surface-variant">Computed Emissions</span>
          <strong className="font-display-lg text-[34px] leading-none font-extrabold text-primary">{record.co2e_kg_display || `${formatNumber(record.co2e_kg, 3)} kg CO2e`}</strong>
          <small className="text-on-surface-variant">{categoryLabels[record.category] || record.category}</small>
        </div>

        {record.parse_warnings?.length > 0 && (
          <div className="my-5 flex gap-3 rounded-xl border border-[#ffd166] bg-[#fff8dc] p-4 text-[#a65f00]">
            <TriangleAlert size={18} />
            <div>
              <strong>Parser warnings</strong>
              <div className="mt-2 flex flex-wrap gap-2">
                {record.parse_warnings.map((warning) => <span className="rounded-full bg-[#fff0bf] px-3 py-1.5 font-label-mono text-[11px] font-bold" key={warning}>{warning}</span>)}
              </div>
            </div>
          </div>
        )}

        <div className="my-6 border-t border-outline-variant">
          {[
            ['Source Type', record.source_type],
            ['Period', record.period_start && record.period_end ? `${record.period_start} to ${record.period_end}` : record.activity_date],
            ['Entity', record.source_entity || '-'],
            ['Description', record.source_description || '-'],
            ['Reference', record.source_reference || '-'],
            ['Raw Quantity', `${record.raw_quantity || '-'} ${record.raw_unit || ''}`],
            ['Normalized', `${record.normalized_quantity || '-'} ${record.normalized_unit || ''}`],
          ].map(([label, value]) => (
            <div className="flex justify-between gap-5 border-b border-outline-variant py-3.5" key={label}>
              <span className="text-sm text-on-surface-variant">{label}</span>
              <strong className="text-right text-on-surface">{value}</strong>
            </div>
          ))}
        </div>

        {!readonly && (
          <div className="mb-5 grid gap-4">
            <div>
              <label className={labelClass}>Corrected Quantity</label>
              <input className={`${inputClass} mt-2`} value={editQty} onChange={(event) => setEditQty(event.target.value)} placeholder={record.normalized_quantity || 'Optional'} />
            </div>
            <div>
              <label className={labelClass}>Unit</label>
              <input className={`${inputClass} mt-2`} value={editUnit} onChange={(event) => setEditUnit(event.target.value)} placeholder={record.normalized_unit || 'Unit'} />
            </div>
            <div>
              <label className={labelClass}>Audit Note</label>
              <textarea className={`${inputClass} mt-2 min-h-24 resize-y`} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Reason or analyst observation..." />
            </div>
          </div>
        )}

        <pre className="max-h-64 overflow-auto rounded-lg border border-outline-variant bg-surface-container-low p-4 font-label-mono text-xs leading-relaxed text-on-surface-variant">{JSON.stringify(record.raw_json, null, 2)}</pre>

        {!readonly && (
          <div className="sticky -bottom-7 mt-5 grid grid-cols-[1fr_1fr_1.4fr] gap-2 bg-surface-container-lowest pt-4">
            <button disabled={loading} className={dangerButtonClass} onClick={() => submit('FLAGGED')}><Flag size={18} />Flag</button>
            <button disabled={loading} className={secondaryButtonClass} onClick={() => submit('REJECTED')}><XCircle size={18} />Reject</button>
            <button disabled={loading} className={primaryButtonClass} onClick={() => submit('APPROVED')}><CheckCircle2 size={18} />Approve</button>
          </div>
        )}
      </aside>
    </div>
  );
};

const ReviewPage = () => {
  const [searchParams] = useSearchParams();
  const [records, setRecords] = useState([]);
  const [selected, setSelected] = useState(null);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null, page: 1 });
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    source_type: '',
    scope: '',
    search: searchParams.get('search') || '',
    batch_id: searchParams.get('batch_id') || '',
  });

  const fetchRecords = useCallback(async (page = 1) => {
    setLoading(true);
    const params = new URLSearchParams({ page });
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.append(key, value);
    });

    try {
      const { data } = await api.get(`/records/?${params}`);
      setRecords(data.results || []);
      setPagination({ 
        count: data.count, 
        next: data.next, 
        previous: data.previous, 
        page,
        total_queue_rows: data.query_total_rows || 0,
        resolved_queue_rows: data.query_resolved_rows || 0
      });
    } catch {
      toast.error('Failed to load review queue', { className: 'toast-error' });
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    const id = window.setTimeout(() => fetchRecords(1), 0);
    return () => window.clearTimeout(id);
  }, [fetchRecords]);

  useEffect(() => {
    const handleGlobalSearch = (event) => {
      const search = event.detail || '';
      setFilters((current) => ({ ...current, search }));
    };
    window.addEventListener('breathesg-global-search', handleGlobalSearch);
    return () => window.removeEventListener('breathesg-global-search', handleGlobalSearch);
  }, []);

  const approveSelected = async () => {
    if (!selectedIds.size) return;
    try {
      const { data } = await api.post('/records/bulk-approve/', {
        record_ids: [...selectedIds],
        note: 'Bulk approved via analyst review',
      });
      toast.success(`Approved ${data.approved} records`, { className: 'toast-success' });
      setSelectedIds(new Set());
      fetchRecords(pagination.page);
    } catch (error) {
      const message = error.response?.data?.message || 'Bulk approval failed';
      toast.error(message, { className: 'toast-error' });
    }
  };

  const flagSelected = async () => {
    const pendingIds = records.filter((record) => selectedIds.has(record.id) && record.status === 'PENDING').map((record) => record.id);
    if (!pendingIds.length) {
      toast.error('Select pending rows to flag', { className: 'toast-error' });
      return;
    }
    try {
      await Promise.all(pendingIds.map((id) => api.patch(`/records/${id}/`, {
        status: 'FLAGGED',
        review_note: 'Flagged for clarification via analyst review',
      })));
      toast.success(`Flagged ${pendingIds.length} records for clarification`, { className: 'toast-success' });
      setSelectedIds(new Set());
      fetchRecords(pagination.page);
    } catch {
      toast.error('Flag action failed', { className: 'toast-error' });
    }
  };

  const exportVisibleRecords = () => {
    if (!records.length) {
      toast.error('No visible records to export', { className: 'toast-error' });
      return;
    }
    const columns = ['period', 'source', 'status', 'quantity', 'unit', 'co2e_kg'];
    const rows = records.map((record) => [
      record.period_start || record.activity_date || '',
      record.source_entity || record.source_type || '',
      record.status || '',
      record.normalized_quantity || '',
      record.normalized_unit || '',
      record.co2e_kg || '',
    ]);
    const csv = [columns, ...rows].map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(',')).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'review-queue.csv';
    link.click();
    URL.revokeObjectURL(url);
  };

  const toggleId = (id) => {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const pendingRows = records.filter((record) => ['PENDING', 'FLAGGED'].includes(record.status));
  const visibleProgress = pagination.total_queue_rows 
    ? Math.round((pagination.resolved_queue_rows / pagination.total_queue_rows) * 100) 
    : 0;

  return (
    <>
      <div className="mb-10 grid grid-cols-4 gap-6 max-xl:grid-cols-2 max-sm:grid-cols-1">
        <StatCard label="Total Rows" value={pagination.count.toLocaleString()} detail="Ready for validation" icon={ListChecks} />
        <StatCard label="Visible Estimates" value={records.filter((r) => r.is_estimated).length} detail="On this result page" icon={TriangleAlert} tone="critical" />
        <StatCard label="Records On Page" value={records.length} detail="Current result view" icon={ShieldCheck} tone="secondary" />
        <StatCard label="Visible Progress" value={`${visibleProgress}%`} detail="Rows resolved" icon={CheckCircle2} tone="inverse" />
      </div>

      <Card className="overflow-hidden p-0">
        <div className="flex min-h-[78px] items-center justify-between gap-4 px-7 max-xl:flex-col max-xl:items-start max-xl:py-5 border-b border-outline-variant">
          <div className="flex items-center gap-4">
            <h2 className="m-0 font-headline-sm text-[28px] font-bold text-primary">Normalization Review Queue</h2>
            <span className="rounded-full bg-secondary-container px-3 py-1.5 font-label-mono text-xs font-bold tracking-[0.05em] text-secondary">In Review</span>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SearchBox value={filters.search} onChange={(search) => setFilters((f) => ({ ...f, search }))} placeholder="Search records..." />
            <select className="h-11 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-on-surface outline-none" value={filters.status} onChange={(event) => setFilters((f) => ({ ...f, status: event.target.value }))}>
              <option value="">All Statuses</option>
              <option value="PENDING">Pending</option>
              <option value="FLAGGED">Flagged</option>
              <option value="APPROVED">Approved</option>
              <option value="REJECTED">Rejected</option>
            </select>
            <button className={secondaryButtonClass} onClick={exportVisibleRecords}><Download size={17} />Export</button>
          </div>
        </div>

        {loading ? (
          <div className="grid min-h-64 place-items-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-outline-variant border-t-primary" /></div>
        ) : records.length === 0 ? (
          <EmptyState title="No records found" text="Adjust filters or upload a new source file." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className={headerCell}><input className="h-[18px] w-[18px] accent-primary" type="checkbox" checked={selectedIds.size === pendingRows.length && pendingRows.length > 0} onChange={() => setSelectedIds(selectedIds.size ? new Set() : new Set(pendingRows.map((row) => row.id)))} /></th>
                  <th className={headerCell}>Period</th>
                  <th className={headerCell}>Source</th>
                  <th className={headerCell}>Read Type</th>
                  <th className={`${headerCell} text-right`}>Usage</th>
                  <th className={`${headerCell} text-right`}>Emissions</th>
                  <th className={headerCell}>Verification</th>
                  <th className={headerCell}>Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant">
                {records.map((record) => (
                  <tr key={record.id} className="even:bg-tertiary-fixed/10 hover:bg-surface-container-low transition-colors">
                    <td className={cell}>{['PENDING', 'FLAGGED'].includes(record.status) && <input className="h-[18px] w-[18px] accent-primary" type="checkbox" checked={selectedIds.has(record.id)} onChange={() => toggleId(record.id)} />}</td>
                    <td className={`${cell} font-label-mono text-on-surface`}>{record.period_start || record.activity_date || '-'}</td>
                    <td className={cell}>
                      <strong className="block text-on-surface">{record.source_entity || record.source_type}</strong>
                      <small className="mt-1 block max-w-64 truncate text-on-surface-variant">{record.source_description || record.ingestion_log_filename}</small>
                    </td>
                    <td className={cell}><StatusChip status={record.status} /></td>
                    <td className={`${cell} text-right font-data-tabular tabular-nums text-on-surface`}>{formatNumber(record.normalized_quantity || 0, 2)} {record.normalized_unit}</td>
                    <td className={`${cell} text-right font-data-tabular tabular-nums text-on-surface`}>{formatNumber((record.co2e_kg || 0) / 1000, 3)}</td>
                    <td className={cell}>{record.parse_warnings?.length ? <TriangleAlert color="#a65f00" /> : <CheckCircle2 className="text-status-verified" />}</td>
                    <td className={cell}>
                      <button className="cursor-pointer inline-flex items-center gap-2 border-0 bg-transparent font-label-mono text-[13px] font-bold text-audit-blue hover:underline" onClick={() => setSelected(record)}><Eye size={15} />View Source</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex min-h-20 items-center justify-end gap-3 border-t border-outline-variant px-6 py-4 max-lg:flex-col max-lg:items-stretch bg-surface-container-lowest">
          <span className="mr-auto rounded-[10px] bg-primary-fixed px-4 py-2.5 font-label-mono text-sm font-bold text-on-primary-fixed-variant max-lg:mr-0">{selectedIds.size} Rows Selected</span>
          <button className={`${secondaryButtonClass} disabled:opacity-50 disabled:cursor-not-allowed`} disabled={selectedIds.size === 0} onClick={() => setSelectedIds(new Set())}>Clear Selection</button>
          <button className={`${dangerButtonClass} disabled:opacity-50 disabled:cursor-not-allowed`} disabled={selectedIds.size === 0} onClick={flagSelected}><Flag size={18} />Flag for Clarification</button>
          <button className={`${primaryButtonClass} disabled:opacity-50 disabled:cursor-not-allowed`} disabled={selectedIds.size === 0} onClick={approveSelected}><CheckCircle2 size={18} />Approve Selected for Audit</button>
        </div>
        <div className="flex items-center justify-end gap-3 border-t border-outline-variant px-6 py-4 max-sm:flex-wrap bg-surface-container/20">
          <span className="mr-auto text-sm text-on-surface-variant font-label-mono">Showing page {pagination.page} | {pagination.count} records</span>
          <button className={secondaryButtonClass} disabled={!pagination.previous} onClick={() => fetchRecords(pagination.page - 1)}>Previous</button>
          <button className={secondaryButtonClass} disabled={!pagination.next} onClick={() => fetchRecords(pagination.page + 1)}>Next</button>
        </div>
      </Card>

      {selected && <RecordDrawer record={selected} onClose={() => setSelected(null)} onRefresh={() => fetchRecords(pagination.page)} />}
    </>
  );
};

export default ReviewPage;
