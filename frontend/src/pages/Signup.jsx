import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserPlus } from 'lucide-react';
import { inputClass, labelClass, primaryButtonClass } from '../components/ui';
import { AuthFrame } from './Login';

const Signup = () => {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: '', email: '', password: '' });
  const [loading, setLoading] = useState(false);

  const submit = (event) => {
    event.preventDefault();
    setLoading(true);
    // Simulate signup
    setTimeout(() => {
      setLoading(false);
      navigate('/login');
    }, 1000);
  };

  return (
    <AuthFrame title="Create workspace" subtitle="Set up your analyst profile for secure enterprise carbon accounting." mode="signup">
      <form className="grid gap-5" onSubmit={submit}>
        <div>
          <label className={labelClass}>Full Name</label>
          <input className={`${inputClass} mt-1.5`} value={form.name} onChange={(event) => setForm((f) => ({ ...f, name: event.target.value }))} placeholder="Jane Doe" required />
        </div>
        <div>
          <label className={labelClass}>Work Email</label>
          <input className={`${inputClass} mt-1.5`} type="email" value={form.email} onChange={(event) => setForm((f) => ({ ...f, email: event.target.value }))} placeholder="jane@breathesg.example" required />
        </div>
        <div>
          <label className={labelClass}>Password</label>
          <input className={`${inputClass} mt-1.5`} type="password" value={form.password} onChange={(event) => setForm((f) => ({ ...f, password: event.target.value }))} placeholder="••••••••" required />
        </div>
        <button className={`${primaryButtonClass} mt-2 w-full`} disabled={loading} type="submit">
          {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <UserPlus size={16} />}
          Create account
        </button>
      </form>
    </AuthFrame>
  );
};

export default Signup;
