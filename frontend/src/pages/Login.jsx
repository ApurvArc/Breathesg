import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, Leaf, LockKeyhole, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import { inputClass, labelClass, primaryButtonClass } from '../components/ui';
import { useAppContext } from '../context/AuthContext';

export const AuthFrame = ({ title, subtitle, children, mode = 'login' }) => (
  <div className="grid min-h-screen grid-cols-[minmax(0,1fr)_480px] bg-background text-on-surface max-lg:grid-cols-1">
    <section className="relative flex min-h-screen flex-col justify-between overflow-hidden border-r border-outline-variant p-10 max-lg:min-h-0 max-lg:gap-8 max-lg:border-r-0 max-lg:border-b max-lg:p-6">
      <div className="relative z-1 flex items-center gap-3 text-primary">
        <div className="grid h-10 w-10 place-items-center rounded-lg bg-primary-container text-on-primary">
          <Leaf size={20} fill="currentColor" />
        </div>
        <div>
          <strong className="block font-headline-sm text-xl leading-none font-extrabold text-primary">Breathe ESG</strong>
          <span className="mt-1 block font-label-mono text-xs font-semibold tracking-[0.06em] text-on-surface-variant opacity-70">Enterprise Audit</span>
        </div>
      </div>
      
      <div className="relative z-1 max-w-[560px]">
        <h1 className="m-0 font-display-lg text-4xl leading-tight font-extrabold text-primary max-lg:text-3xl">Carbon intelligence with an audit trail.</h1>
        <p className="mt-4 max-w-[480px] text-lg font-body-lg leading-relaxed text-on-surface-variant">Normalize SAP, utility, and travel data into a reviewable carbon ledger with calm, precise enterprise workflows.</p>
      </div>
      
      <div className="relative z-1 grid grid-cols-3 gap-4 max-lg:grid-cols-1">
        {[['3', 'Source clusters'], ['99.8%', 'Review precision'], ['24/7', 'Audit trace']].map(([value, label]) => (
          <div className="rounded-lg border border-outline-variant bg-surface-container-lowest p-4" key={label}>
            <strong className="block font-display-lg text-2xl leading-none font-extrabold text-primary">{value}</strong>
            <span className="mt-1.5 block font-label-mono text-[10px] font-bold uppercase tracking-[0.06em] text-on-surface-variant">{label}</span>
          </div>
        ))}
      </div>
    </section>
    
    <section className="grid min-h-screen place-items-center bg-surface-container-lowest p-8 max-lg:min-h-0">
      <div className="w-full max-w-[360px]">
        <ShieldCheck size={28} className="text-primary" />
        <h2 className="mt-4 font-headline-sm text-2xl font-extrabold text-primary">{title}</h2>
        <p className="mb-6 mt-2 font-body-md text-sm leading-relaxed text-on-surface-variant">{subtitle}</p>
        
        {children}
        
        <div className="mt-6 text-center font-body-md text-sm text-on-surface-variant">
          {mode === 'login' ? (
            <>Need an analyst workspace? <Link className="font-extrabold text-primary no-underline hover:opacity-80" to="/signup">Create account</Link></>
          ) : (
            <>Already have access? <Link className="font-extrabold text-primary no-underline hover:opacity-80" to="/login">Sign in</Link></>
          )}
        </div>
      </div>
    </section>
  </div>
);

const Login = () => {
  const { login } = useAppContext();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: '', password: '' });
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    setLoading(true);
    try {
      await login(form.username, form.password);
      navigate('/dashboard');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Invalid credentials', { className: 'toast-error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthFrame title="Welcome back" subtitle="Sign in to continue normalization review and ledger approval." mode="login">
      <form className="grid gap-4" onSubmit={submit}>
        <div>
          <label className={labelClass}>Email / Username</label>
          <input className={`${inputClass} mt-1.5`} value={form.username} onChange={(event) => setForm((f) => ({ ...f, username: event.target.value }))} placeholder="admin@esg.com" autoComplete="username" required />
        </div>
        <div>
          <label className={labelClass}>Password</label>
          <div className="relative mt-1.5">
            <input className={`${inputClass} pr-10`} type={showPw ? 'text' : 'password'} value={form.password} onChange={(event) => setForm((f) => ({ ...f, password: event.target.value }))} placeholder="••••••••" autoComplete="current-password" required />
            <button className="cursor-pointer absolute top-1/2 right-2 grid h-8 w-8 -translate-y-1/2 place-items-center border-0 bg-transparent text-outline" type="button" onClick={() => setShowPw((value) => !value)}>
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </div>
        <button className={`${primaryButtonClass} mt-2 w-full`} disabled={loading} type="submit">
          {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <LockKeyhole size={16} />}
          Sign in
        </button>
      </form>
      <div className="mt-5 rounded border border-outline-variant bg-surface-container-low p-3 font-body-md text-xs text-on-surface-variant">
        Demo credentials: <strong>admin@esg.com</strong> / <strong>admin123</strong>
      </div>
    </AuthFrame>
  );
};

export default Login;
