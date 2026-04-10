import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import {
  FileText,
  FilePdf,
  FileXls,
  FileDoc,
  UploadSimple,
  Plus,
  Trash,
  ArrowClockwise,
  Brain,
  Sparkle,
  X,
  FloppyDisk,
  Globe,
} from '@phosphor-icons/react';

import { clientAPI } from '../api/client';
import Card, { CardHeader, CardAction } from '../components/ui/Card';
import Button from '../components/ui/Button';
import StatCard from '../components/ui/StatCard';

/* ─────────────── Helpers ─────────────── */

const fileIcon = (type) => {
  switch ((type || '').toLowerCase()) {
    case 'pdf':                 return FilePdf;
    case 'xls': case 'xlsx':    return FileXls;
    case 'doc': case 'docx':    return FileDoc;
    default:                    return FileText;
  }
};

const fileAccent = (type) => {
  switch ((type || '').toLowerCase()) {
    case 'pdf':                 return 'rose';
    case 'xls': case 'xlsx':    return 'sage';
    case 'doc': case 'docx':    return 'iris';
    case 'text':                return 'amber';
    default:                    return 'iris';
  }
};

const ACCENT_BORDER = {
  rose:  'border-rose text-rose',
  sage:  'border-sage text-sage',
  iris:  'border-iris text-iris',
  amber: 'border-amber text-amber',
};

const formatSize = (bytes) => {
  if (!bytes) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
};

/* ─────────────── Page ─────────────── */

const TrainingPage = () => {
  const { t } = useTranslation();
  const [files, setFiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadErrors, setUploadErrors] = useState([]);
  const [textModal, setTextModal] = useState(false);
  const [webModal, setWebModal] = useState(false);

  const [prompt, setPrompt] = useState('');
  const [originalPrompt, setOriginalPrompt] = useState('');
  const [promptSaving, setPromptSaving] = useState(false);
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    loadDocuments(true);
    loadPrompt();
  }, []);

  useEffect(() => {
    if (!files.some((f) => !f.is_processed)) return;
    const iv = setInterval(() => loadDocuments(false), 5000);
    return () => clearInterval(iv);
  }, [files]);

  const loadDocuments = async (withLoader = true) => {
    try {
      if (withLoader) setLoading(true);
      const { data } = await clientAPI.getDocuments();
      setFiles((data || []).map((doc) => {
        const ft = doc.file_type || 'unknown';
        const isText = ft === 'txt' && (!doc.file || doc.file === '');
        return {
          id: doc.id,
          name: doc.title || doc.file_name || 'Untitled',
          size: doc.file_size || 0,
          type: isText ? 'text' : ft,
          uploadedAt: doc.uploaded_at || new Date().toISOString(),
          is_processed: doc.is_processed,
        };
      }));
    } catch (e) {
      console.error('Failed to load documents:', e);
    } finally {
      if (withLoader) setLoading(false);
    }
  };

  const loadPrompt = async () => {
    try {
      const { data } = await clientAPI.getMe();
      const p = data?.custom_system_prompt || '';
      setPrompt(p);
      setOriginalPrompt(p);
    } catch (e) {
      console.error('Failed to load prompt:', e);
    }
  };

  const handleFiles = async (fileList) => {
    setUploading(true);
    setUploadErrors([]);
    for (const f of Array.from(fileList)) {
      try {
        await clientAPI.uploadDocument(f, f.name, null);
      } catch (e) {
        const msg = e?.response?.data?.error || e?.response?.data?.message || e.message || 'Unknown';
        setUploadErrors((prev) => [...prev, { id: Date.now() + Math.random(), name: f.name, message: msg }]);
      }
    }
    setUploading(false);
    loadDocuments(true);
  };

  const handleDelete = async (id) => {
    if (!confirm(t('common.delete') + '?')) return;
    try {
      await clientAPI.deleteDocument(id);
      setFiles((fs) => fs.filter((f) => f.id !== id));
    } catch (e) {
      alert(e?.response?.data?.error || 'Failed');
    }
  };

  const savePrompt = async () => {
    setPromptSaving(true);
    try {
      await clientAPI.updateMe({ custom_system_prompt: prompt });
      setOriginalPrompt(prompt);
    } catch (e) {
      alert(e?.response?.data?.error || 'Failed to save prompt');
    } finally {
      setPromptSaving(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await clientAPI.syncData();
      loadDocuments(true);
    } catch (e) {
      alert(e?.response?.data?.error || 'Failed to sync');
    } finally {
      setSyncing(false);
    }
  };

  const stats = [
    { accent: 'iris',  icon: FileText,  label: 'Knowledge Docs', value: files.length.toString(),                         delta: files.filter((f) => f.is_processed).length + ' processed', trend: 'up' },
    { accent: 'sage',  icon: Sparkle,   label: 'Indexed',        value: files.filter((f) => f.is_processed).length.toString(), delta: files.filter((f) => !f.is_processed).length + ' pending',  trend: 'up' },
    { accent: 'amber', icon: Brain,     label: 'Prompt Length',  value: prompt.length.toLocaleString(),                  delta: originalPrompt !== prompt ? 'unsaved changes' : 'saved',   trend: originalPrompt !== prompt ? 'down' : 'up' },
    { accent: 'rose',  icon: UploadSimple, label: 'Upload Errors', value: uploadErrors.length.toString(),                delta: uploadErrors.length ? 'review below' : 'clean run',         trend: uploadErrors.length ? 'down' : 'up' },
  ];

  return (
    <div className="max-w-[1200px] mx-auto">
      {/* ── Header ── */}
      <div className="flex justify-between items-start mb-8 animate-fade-up">
        <div>
          <h1 className="text-[28px] font-bold tracking-tightest">
            {t('training.title') || 'Jeevs'}
          </h1>
          <div className="font-mono text-[13px] text-fog mt-1">
            knowledge · persona · training room
          </div>
        </div>
        <div className="hidden md:flex gap-2.5">
          <Button variant="amber" icon={Globe} onClick={() => setWebModal(true)}>
            Crawl URL
          </Button>
          <Button variant="pink" icon={Plus} onClick={() => setTextModal(true)}>
            Add Text
          </Button>
          <Button variant="green" icon={ArrowClockwise} onClick={handleSync}>
            {syncing ? 'Syncing…' : 'Sync'}
          </Button>
        </div>
      </div>

      {/* ── Stats ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {stats.map((s) => <StatCard key={s.label} {...s} />)}
      </div>

      {/* ── Main grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mb-8">
        {/* Left column — upload + files */}
        <div className="lg:col-span-2 space-y-5">
          <DropZone onFiles={handleFiles} uploading={uploading} />

          {uploadErrors.length > 0 && (
            <Card accent="rose">
              <CardHeader
                title="Upload Errors"
                action={<CardAction onClick={() => setUploadErrors([])}>dismiss</CardAction>}
              />
              <div className="space-y-2">
                {uploadErrors.map((e) => (
                  <div key={e.id} className="flex items-start gap-3 py-2">
                    <X size={16} weight="bold" className="text-rose mt-0.5 shrink-0" />
                    <div className="flex-1">
                      <div className="text-[13px] font-medium text-ink">{e.name}</div>
                      <div className="font-mono text-[11px] text-fog">{e.message}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          <FileListCard files={files} loading={loading} onDelete={handleDelete} />

          {/* Prompt editor */}
          <Card accent="iris">
            <CardHeader
              title="System Prompt"
              action={
                <span className="font-mono text-[11px] text-fog">
                  {prompt.length} chars
                </span>
              }
            />
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Describe how Jeevs should behave: tone, persona, boundaries, escalation rules…"
              className="w-full h-64 p-3.5 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink font-sans resize-y leading-relaxed
                         focus:outline-none focus:border-iris transition-colors"
            />
            <div className="flex items-center justify-between mt-4">
              <span className={`font-mono text-[11px] ${
                originalPrompt !== prompt ? 'text-rose' : 'text-sage'
              }`}>
                {originalPrompt !== prompt ? '● unsaved changes' : '● in sync'}
              </span>
              <Button variant="green" icon={FloppyDisk} onClick={savePrompt}>
                {promptSaving ? 'Saving…' : 'Save Prompt'}
              </Button>
            </div>
          </Card>
        </div>

        {/* Right column — coach tips */}
        <div className="space-y-5">
          <Card accent="sage">
            <CardHeader title="Training Tips" />
            <ul className="space-y-3 text-[13px] text-slate leading-relaxed">
              <li className="flex gap-2.5">
                <span className="text-sage font-mono shrink-0">01</span>
                Upload authoritative sources — menus, price lists, FAQs, T&Cs.
              </li>
              <li className="flex gap-2.5">
                <span className="text-sage font-mono shrink-0">02</span>
                Keep the system prompt short and declarative. Jeevs reads it before every reply.
              </li>
              <li className="flex gap-2.5">
                <span className="text-sage font-mono shrink-0">03</span>
                Run Sync after every batch of uploads to rebuild the vector index.
              </li>
              <li className="flex gap-2.5">
                <span className="text-sage font-mono shrink-0">04</span>
                Use the Sandbox tab to rehearse before going live on channels.
              </li>
            </ul>
          </Card>

          <Card accent="amber">
            <CardHeader title="Supported Formats" />
            <div className="grid grid-cols-2 gap-2">
              {['PDF', 'DOCX', 'TXT', 'XLSX', 'JSON', 'CSV', 'HTML', 'MD'].map((f) => (
                <div key={f} className="label-mono px-2.5 py-2 border-[1.5px] border-rule rounded-sm text-center">
                  {f}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {/* ── Modals ── */}
      {textModal && (
        <TextAddModal
          onClose={() => setTextModal(false)}
          onSaved={() => { setTextModal(false); loadDocuments(true); }}
        />
      )}
      {webModal && (
        <WebCrawlModal
          onClose={() => setWebModal(false)}
          onSaved={() => { setWebModal(false); loadDocuments(true); }}
        />
      )}
    </div>
  );
};

/* ─────────────── Drop zone ─────────────── */

const DropZone = ({ onFiles, uploading }) => {
  const [drag, setDrag] = useState(false);
  const inputRef = useRef(null);

  return (
    <Card>
      <CardHeader title="Upload Knowledge" />
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); onFiles(e.dataTransfer.files); }}
        className={`rounded-lg border-[2px] border-dashed p-10 text-center
                    transition-colors duration-200 cursor-pointer
                    ${drag ? 'border-iris bg-mist' : 'border-rule hover:border-iris hover:bg-linen'}
                    ${uploading ? 'opacity-60 pointer-events-none' : ''}`}
        onClick={() => inputRef.current?.click()}
      >
        <UploadSimple size={40} weight="light" className="text-iris mx-auto mb-3" />
        <p className="text-[14px] text-ink font-medium mb-1">
          {uploading ? 'Uploading…' : 'Drag & drop or click to select files'}
        </p>
        <p className="font-mono text-[11px] text-fog">
          PDF · DOCX · TXT · XLSX · JSON · up to 25 MB
        </p>
        <input
          ref={inputRef}
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.doc,.docx,.txt,.xls,.xlsx,.json,.csv,.html,.md"
          onChange={(e) => { onFiles(e.target.files); e.target.value = ''; }}
          disabled={uploading}
        />
      </div>
    </Card>
  );
};

/* ─────────────── File list card ─────────────── */

const FileListCard = ({ files, loading, onDelete }) => {
  return (
    <Card>
      <CardHeader
        title="Knowledge Library"
        action={<span className="label-mono">{files.length} files</span>}
      />
      {loading ? (
        <p className="label-mono py-8 text-center">loading…</p>
      ) : files.length === 0 ? (
        <p className="label-mono py-8 text-center">no documents yet</p>
      ) : (
        <div className="divide-y divide-rule">
          {files.map((f) => {
            const Icon = fileIcon(f.type);
            const accent = fileAccent(f.type);
            return (
              <div key={f.id} className="flex items-center gap-3.5 py-3">
                <div className={`shrink-0 w-[38px] h-[38px] rounded-md border-2
                                ${ACCENT_BORDER[accent]}
                                flex items-center justify-center`}>
                  <Icon size={20} weight="light" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-[14px] font-medium text-ink truncate">{f.name}</div>
                  <div className="font-mono text-[11px] text-fog">
                    {f.type?.toUpperCase() || '—'} · {formatSize(f.size)}
                  </div>
                </div>
                <span className={`pill ${f.is_processed ? 'pill-on' : 'pill-warning'}`}>
                  {f.is_processed ? 'indexed' : 'processing'}
                </span>
                <button
                  onClick={() => onDelete(f.id)}
                  className="text-fog hover:text-rose transition-colors cursor-pointer p-1.5"
                  aria-label="Delete document"
                >
                  <Trash size={16} weight="light" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </Card>
  );
};

/* ─────────────── Text add modal ─────────────── */

const TextAddModal = ({ onClose, onSaved }) => {
  const [title, setTitle] = useState('');
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!title.trim() || !text.trim()) return;
    setSaving(true);
    try {
      await clientAPI.uploadTextDocument(title.trim(), text.trim());
      onSaved();
    } catch (e) {
      alert(e?.response?.data?.error || 'Failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
      <div className="surface p-6 w-full max-w-2xl animate-fade-up">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-[16px] font-semibold text-ink">Add Text Knowledge</h3>
          <button onClick={onClose} className="text-fog hover:text-ink cursor-pointer">
            <X size={20} weight="light" />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <div className="label-mono mb-1.5">Title</div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Pricing Policy 2026"
              className="w-full px-3 py-2 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink focus:outline-none focus:border-iris transition-colors"
            />
          </div>
          <div>
            <div className="label-mono mb-1.5">Content</div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste any text Jeevs should know…"
              className="w-full h-56 p-3 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink resize-y focus:outline-none focus:border-iris transition-colors"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2.5 mt-5">
          <Button variant="amber" onClick={onClose}>Cancel</Button>
          <Button variant="green" icon={FloppyDisk} onClick={save}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  );
};

/* ─────────────── Web crawl modal ─────────────── */

const WebCrawlModal = ({ onClose, onSaved }) => {
  const [url, setUrl] = useState('');
  const [title, setTitle] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    if (!url.trim()) return;
    setSaving(true);
    try {
      // Reuse text upload if web crawl API is unavailable — pass URL as reference
      await clientAPI.uploadTextDocument(
        title.trim() || url.trim(),
        `[Web source] ${url.trim()}\n\nAdd crawled content manually or via backend crawler.`
      );
      onSaved();
    } catch (e) {
      alert(e?.response?.data?.error || 'Failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/30 backdrop-blur-[2px] p-4">
      <div className="surface p-6 w-full max-w-xl animate-fade-up">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-[16px] font-semibold text-ink">Crawl Web Page</h3>
          <button onClick={onClose} className="text-fog hover:text-ink cursor-pointer">
            <X size={20} weight="light" />
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <div className="label-mono mb-1.5">URL</div>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/pricing"
              className="w-full px-3 py-2 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink font-mono focus:outline-none focus:border-iris transition-colors"
            />
          </div>
          <div>
            <div className="label-mono mb-1.5">Title (optional)</div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Pricing page"
              className="w-full px-3 py-2 bg-cream border-[1.5px] border-rule rounded-sm
                         text-[13px] text-ink focus:outline-none focus:border-iris transition-colors"
            />
          </div>
        </div>
        <div className="flex justify-end gap-2.5 mt-5">
          <Button variant="amber" onClick={onClose}>Cancel</Button>
          <Button variant="green" icon={FloppyDisk} onClick={save}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default TrainingPage;
