import { User, ShieldCheck, Mail } from 'lucide-react';
import { useAppContext } from '../context/AuthContext';
import { Card, labelClass, inputClass } from '../components/ui';

const SettingsPage = () => {
  const { user } = useAppContext();

  return (
    <div className="grid gap-6 max-w-2xl mx-auto">
      <div className="mb-2">
        <h2 className="m-0 font-display text-2xl font-bold text-primary">Workspace Profile</h2>
        <p className="mt-1 text-sm text-on-surface-variant">View your analyst role and tenant assignments.</p>
      </div>

      <Card>
        <div className="mb-6 flex items-center gap-3">
          <User size={20} className="text-primary" />
          <h3 className="m-0 font-display text-lg font-bold">Identity</h3>
        </div>
        <div className="grid grid-cols-2 gap-5 max-sm:grid-cols-1">
          <div>
            <label className={labelClass}>Username</label>
            <input className={`${inputClass} mt-2 bg-surface-container-low`} value={user?.username || ''} readOnly />
          </div>
          <div>
            <label className={labelClass}>Full Name</label>
            <input className={`${inputClass} mt-2 bg-surface-container-low`} value={user?.full_name || user?.username || ''} readOnly />
          </div>
        </div>
      </Card>

      <Card>
        <div className="mb-6 flex items-center gap-3">
          <ShieldCheck size={20} className="text-primary" />
          <h3 className="m-0 font-display text-lg font-bold">Access & Roles</h3>
        </div>
        <div className="grid grid-cols-2 gap-5 max-sm:grid-cols-1">
          <div>
            <label className={labelClass}>System Role</label>
            <input className={`${inputClass} mt-2 bg-surface-container-low`} value={user?.role || 'ESG Analyst'} readOnly />
          </div>
          <div>
            <label className={labelClass}>Tenant Assignment</label>
            <input className={`${inputClass} mt-2 bg-surface-container-low`} value={user?.tenant?.name || 'Global Workspace'} readOnly />
          </div>
        </div>
      </Card>

      <Card className="flex flex-wrap items-center justify-between gap-5 mt-4">
        <div>
          <h3 className="m-0 font-display text-lg font-bold text-primary">Support</h3>
          <p className="mb-0 mt-1 text-sm text-on-surface-variant">For permission changes, contact your administrator.</p>
        </div>
        <a className="inline-flex items-center justify-center gap-2 rounded-lg border border-outline-variant bg-transparent px-4 py-2 text-sm font-bold text-primary no-underline transition hover:bg-surface-container" href="mailto:support@breathesg.example">
          <Mail size={16} /> Contact Admin
        </a>
      </Card>
    </div>
  );
};

export default SettingsPage;
