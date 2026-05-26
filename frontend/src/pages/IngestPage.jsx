import { useRef, useState } from 'react';
import { ArrowRight, Building2, CalendarDays, CheckCircle2, Code2, GitBranch, Plane, UploadCloud, Zap } from 'lucide-react';
import toast from 'react-hot-toast';
import { useNavigate } from 'react-router-dom';
import api from '../configs/api';
import { Card, StatusChip, ghostButtonClass, inputClass, labelClass, primaryButtonClass } from '../components/ui';

const sources = [
  ['SAP', 'SAP ERP Export', 'MB51 flat-file CSV with multilingual headers and locale-aware decimals.', Building2],
  ['UTILITY', 'Utility Electricity', 'Green Button, Octopus UK half-hourly, ESPM, and monthly billing.', Zap],
  ['TRAVEL', 'Corporate Travel', 'Concur/Navan travel with air, hotel, rail, taxi, and rentals.', Plane],
];

const IngestPage = () => {
  const navigate = useNavigate();
  const [selectedType, setSelectedType] = useState('SAP');
  const [region, setRegion] = useState('GB');
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const fileRef = useRef(null);

  const uploadFile = async (file) => {
    if (!file) return;
    if (!file.name.match(/\.(csv|txt|tsv)$/i)) {
      toast.error('Only CSV, TSV, or TXT files are supported', { className: 'toast-error' });
      return;
    }

    setUploading(true);
    setResult(null);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('source_type', selectedType);
    formData.append('grid_region_code', region);
    formData.append('facility_country', region === 'US' ? 'US' : 'GB');

    try {
      const { data } = await api.post('/batches/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult({ success: true, batch: data.data });
      toast.success('Ingestion complete', { className: 'toast-success' });
    } catch (error) {
      const message = error.response?.data?.message || 'Upload failed';
      setResult({ success: false, error: message });
      toast.error(message, { className: 'toast-error' });
    } finally {
      setUploading(false);
    }
  };

  return (
    <>
      <Card>
        <div className="grid grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)] items-start gap-8 max-lg:grid-cols-1">
          <div>
            <h2 className="m-0 font-display text-2xl font-bold text-primary">Configure Data Extraction</h2>
            <p className="mt-2 text-sm text-on-surface-variant">Establish the source type, reporting bounds, and file package for ingestion.</p>
          </div>
          <div className="grid min-h-32 place-items-center content-center gap-2 rounded-xl border border-outline-variant bg-surface-container text-center text-primary p-4">
            <UploadCloud size={28} />
            <strong className="text-sm">Ingestion Gateway</strong>
            <span className="max-w-80 text-xs text-on-surface-variant">Status: <b className="text-primary">READY</b>. Parser token valid for current session.</span>
          </div>
        </div>

        <div className="my-8 grid grid-cols-3 gap-4 max-lg:grid-cols-1">
          {sources.map(([id, title, text, Icon]) => {
            const isSelected = selectedType === id;
            return (
              <button
                key={id}
                type="button"
                className={`cursor-pointer relative grid gap-2 rounded-xl border p-5 text-left transition-all duration-200 ${
                  isSelected 
                    ? '-translate-y-1 border-2 border-primary bg-primary-container shadow-lg shadow-primary/10' 
                    : 'border border-outline-variant bg-surface-container-lowest hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md'
                }`}
                onClick={() => setSelectedType(id)}
              >
                {isSelected && (
                  <div className="absolute right-4 top-4">
                    <CheckCircle2 size={22} className="fill-on-primary-container text-primary-container" />
                  </div>
                )}
                <Icon size={24} className={isSelected ? 'text-on-primary-container' : 'text-outline'} />
                <strong className={`font-display text-base mt-1 ${isSelected ? 'text-white font-extrabold' : 'text-on-surface font-bold'}`}>
                  {title}
                </strong>
                <span className={`text-sm leading-relaxed pr-6 ${isSelected ? 'text-on-primary-container' : 'text-on-surface-variant'}`}>
                  {text}
                </span>
              </button>
            );
          })}
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_minmax(320px,0.8fr)] items-start gap-8 max-lg:grid-cols-1">
          <div className="grid gap-5">
            <div>
              <label className={labelClass}>Region Focus</label>
              <select className={`${inputClass} mt-1.5`} value={region} onChange={(e) => setRegion(e.target.value)}>
                <option value="GB">United Kingdom / GB Grid</option>
                <option value="US">United States / eGRID</option>
                <option value="GLOBAL">Global / Multi-market</option>
              </select>
            </div>
          </div>

          <div
            className={`grid min-h-48 place-items-center content-center gap-2 rounded-xl border border-dashed text-center text-primary transition ${dragOver ? 'border-secondary bg-secondary-container text-on-secondary-container' : 'border-outline bg-surface-container-low'}`}
            onClick={() => fileRef.current?.click()}
            onDrop={(event) => {
              event.preventDefault();
              setDragOver(false);
              uploadFile(event.dataTransfer.files[0]);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
          >
            <input ref={fileRef} type="file" accept=".csv,.txt,.tsv" hidden onChange={(event) => uploadFile(event.target.files[0])} />
            {uploading ? (
              <>
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-surface-variant border-t-primary mb-1" />
                <strong className="text-sm">Parsing and normalizing...</strong>
                <span className="text-xs text-on-surface-variant">Detecting format, units, and emissions factors.</span>
              </>
            ) : (
              <>
                <UploadCloud size={28} />
                <strong className="text-sm">Drop {selectedType} source file here</strong>
                <span className="text-xs text-on-surface-variant">CSV, TSV, or TXT. Max upload 50MB.</span>
              </>
            )}
          </div>
        </div>

        {result && (
          <div className={`mt-6 flex items-center gap-4 rounded-xl p-4 text-sm ${result.success ? 'bg-status-verified/10 text-status-verified border border-status-verified/20' : 'bg-error-container text-status-critical border border-status-critical/20'}`}>
            {result.success ? <CheckCircle2 size={20} /> : <UploadCloud size={20} />}
            <div>
              <strong className="block">{result.success ? result.batch.original_filename : 'Ingestion failed'}</strong>
              <span className="mt-1 flex flex-wrap items-center gap-2 text-on-surface-variant">
                {result.success ? `${result.batch.total_rows} rows processed, ${result.batch.flagged_rows} flagged.` : result.error}
                {result.success && <StatusChip status={result.batch.status} />}
              </span>
            </div>
          </div>
        )}

        <div className="mt-8 flex justify-end gap-3 border-t border-outline-variant pt-6">
          <button className={ghostButtonClass} type="button" onClick={() => setResult(null)}>Cancel</button>
          <button className={primaryButtonClass} type="button" onClick={() => navigate('/review')}>
            View Queue <ArrowRight size={16} />
          </button>
        </div>
      </Card>
    </>
  );
};

export default IngestPage;
