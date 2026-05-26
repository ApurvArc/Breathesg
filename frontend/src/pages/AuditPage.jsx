import { useCallback, useEffect, useState } from 'react';
import { Activity, FileClock, History, LockKeyhole, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../configs/api';
import { AuditActionChip, Card, EmptyState, StatCard, secondaryButtonClass } from '../components/ui';
import { formatDate } from '../utils/format';

const cell = 'border-t border-outline-variant px-6 py-3 align-middle text-sm';
const headerCell = `${cell} bg-surface-container-highest text-left font-mono text-[11px] uppercase tracking-[0.05em] text-on-surface-variant`;

const AuditPage = () => {
  const [logs, setLogs] = useState([]);
  const [selected, setSelected] = useState(null);
  const [pagination, setPagination] = useState({ count: 0, next: null, previous: null, page: 1 });
  const [loading, setLoading] = useState(true);

  const fetchLogs = useCallback(async (page = 1) => {
    setLoading(true);
    try {
      const { data } = await api.get(`/audit-log/?page=${page}`);
      setLogs(data.results || []);
      setPagination({ 
        count: data.count, 
        next: data.next, 
        previous: data.previous, 
        page,
        review_count: data.review_count || 0,
        lock_count: data.lock_count || 0,
        edit_count: data.edit_count || 0,
      });
    } catch {
      toast.error('Failed to load audit log', { className: 'toast-error' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const id = window.setTimeout(() => fetchLogs(1), 0);
    return () => window.clearTimeout(id);
  }, [fetchLogs]);

  return (
    <>
      <div className="mb-8 grid grid-cols-4 gap-6 max-xl:grid-cols-2 max-sm:grid-cols-1">
        <StatCard label="Audit Events" value={pagination.count} detail="Immutable signal stream" icon={History} />
        <StatCard label="Review Events" value={pagination.review_count || 0} detail="Analyst actions" icon={ShieldCheck} tone="secondary" />
        <StatCard label="Locked Batches" value={pagination.lock_count || 0} detail="Ready for evidence pack" icon={LockKeyhole} tone="blue" />
        <StatCard label="System Changes" value={pagination.edit_count || 0} detail="Tracked field diffs" icon={FileClock} tone="critical" />
      </div>

      <Card className="overflow-hidden p-0">
        <div className="flex min-h-[72px] items-center px-6">
          <div className="flex items-center gap-3">
            <Activity size={24} className="text-primary" />
            <div>
              <h2 className="m-0 font-display text-xl font-bold text-primary">Immutable Audit Trail</h2>
              <span className="mt-1 block text-sm text-on-surface-variant">Every event is recorded with target, user, timestamp, and JSON diff.</span>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="grid min-h-48 place-items-center"><div className="h-6 w-6 animate-spin rounded-full border-2 border-surface-variant border-t-primary" /></div>
        ) : logs.length === 0 ? (
          <EmptyState title="No audit events yet" text="Ingest, review, or approve records to create audit events." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr>
                  <th className={headerCell}>Timestamp</th>
                  <th className={headerCell}>Action</th>
                  <th className={headerCell}>Target</th>
                  <th className={headerCell}>User</th>
                  <th className={headerCell}>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="cursor-pointer even:bg-surface-container/50 hover:bg-surface-container-low transition-colors" onClick={() => setSelected(selected?.id === log.id ? null : log)}>
                    <td className={`${cell} font-mono text-[11px]`}>{new Date(log.timestamp).toLocaleString()}</td>
                    <td className={cell}><AuditActionChip action={log.action} label={log.action_display} /></td>
                    <td className={cell}>
                      <strong className="block text-on-surface">{log.target_type}</strong>
                      <small className="mt-1 block font-mono text-[11px] text-on-surface-variant">#{log.target_id?.slice(0, 8)}</small>
                    </td>
                    <td className={cell}>{log.user_name || 'System'}</td>
                    <td className={cell}>
                      <span className="font-mono text-[11px] text-on-surface-variant">
                        {Object.entries(log.after_json || {}).slice(0, 2).map(([key, value]) => `${key}: ${String(value).slice(0, 24)}`).join(' | ') || log.action_display}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="flex items-center justify-end gap-3 border-t border-outline-variant px-6 py-3 max-sm:flex-wrap bg-surface-container-lowest">
          <span className="mr-auto text-xs text-on-surface-variant">Showing page {pagination.page} of {Math.max(1, Math.ceil(pagination.count / 50))} | {pagination.count} events</span>
          <button className={`${secondaryButtonClass} h-8 min-h-0 py-0`} disabled={!pagination.previous} onClick={() => fetchLogs(pagination.page - 1)}>Previous</button>
          <button className={`${secondaryButtonClass} h-8 min-h-0 py-0`} disabled={!pagination.next} onClick={() => fetchLogs(pagination.page + 1)}>Next</button>
        </div>
      </Card>

      {selected && (
        <Card className="mt-6 p-6">
          <div className="mb-4 flex items-center justify-between gap-5">
            <div>
              <div className="font-mono text-[11px] font-bold uppercase tracking-[0.08em] text-outline">Event Detail</div>
              <h2 className="mt-1.5 font-display text-xl font-bold text-primary m-0">{selected.action_display || selected.action}</h2>
            </div>
            <span className="text-sm text-on-surface-variant">{formatDate(selected.timestamp)}</span>
          </div>
          <pre className="max-h-80 overflow-auto rounded-lg border border-outline-variant bg-surface-container-low p-4 font-mono text-[11px] leading-relaxed text-on-surface-variant">{JSON.stringify({
            id: selected.id,
            action: selected.action,
            target_type: selected.target_type,
            target_id: selected.target_id,
            before: selected.before_json,
            after: selected.after_json,
            note: selected.note,
          }, null, 2)}</pre>
        </Card>
      )}
    </>
  );
};

export default AuditPage;
