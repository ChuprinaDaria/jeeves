import { useState } from 'react';
import { Mail, FileSpreadsheet, FileText, Search, Download, ChevronDown, ChevronUp, Star } from 'lucide-react';

const STATUS_COLORS = {
  new:       'bg-blue-500/20 text-blue-400',
  contacted: 'bg-amber-500/20 text-amber-400',
  qualified: 'bg-emerald-500/20 text-emerald-400',
  converted: 'bg-violet-500/20 text-violet-400',
  lost:      'bg-gray-500/20 text-gray-400',
};

const LeadCard = ({ lead, style }) => (
  <div
    className="chat-tool-node border-l-4 border-l-amber-400 rounded-xl border border-gray-200 dark:border-gray-700/50 bg-white/90 dark:bg-gray-800/90 p-3"
    style={style}
  >
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center gap-2">
        <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium ${STATUS_COLORS[lead.status] || STATUS_COLORS.new}`}>
          {lead.status || 'new'}
        </span>
        {lead.heat != null && (
          <div className="flex items-center gap-0.5">
            {[1, 2, 3, 4, 5].map(i => (
              <Star key={i} size={10} className={i <= lead.heat ? 'text-amber-400 fill-amber-400' : 'text-gray-600'} />
            ))}
          </div>
        )}
      </div>
      {lead.phone && <span className="text-[10px] text-gray-400">{lead.phone}</span>}
    </div>
    <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{lead.name || 'Unknown'}</p>
    <p className="text-xs text-gray-500 dark:text-gray-400">
      {[lead.email, lead.company].filter(Boolean).join(' · ')}
    </p>
  </div>
);

const FileCard = ({ file, style }) => {
  const Icon = file.type === 'spreadsheet' ? FileSpreadsheet : FileText;
  return (
    <div
      className="chat-tool-node border-l-4 border-l-emerald-400 rounded-xl border border-gray-200 dark:border-gray-700/50 bg-white/90 dark:bg-gray-800/90 p-3 flex items-center justify-between"
      style={style}
    >
      <div className="flex items-center gap-2">
        <Icon size={16} className="text-emerald-400" />
        <div>
          <p className="text-sm font-medium text-gray-900 dark:text-gray-100">{file.name}</p>
          {file.size && <p className="text-[10px] text-gray-400">{file.size}</p>}
        </div>
      </div>
      {file.url && (
        <a
          href={file.url}
          download
          className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 text-xs hover:bg-emerald-500/20 transition cursor-pointer"
        >
          <Download size={12} /> Download
        </a>
      )}
    </div>
  );
};

const EmailCard = ({ email, style }) => (
  <div
    className="chat-tool-node border-l-4 border-l-emerald-400 rounded-xl border border-gray-200 dark:border-gray-700/50 bg-white/90 dark:bg-gray-800/90 p-3"
    style={style}
  >
    <div className="flex items-center justify-between mb-1">
      <div className="flex items-center gap-2">
        <Mail size={14} className="text-emerald-400" />
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Email Sent</span>
      </div>
      <div className="w-4 h-4 rounded-full bg-emerald-500/20 flex items-center justify-center">
        <span className="text-emerald-400 text-[10px]">✓</span>
      </div>
    </div>
    {email.to && <p className="text-xs text-gray-500 dark:text-gray-400">To: {email.to}</p>}
    {email.subject && <p className="text-xs text-gray-500 dark:text-gray-400">Subject: {email.subject}</p>}
    {email.body && <p className="text-xs text-gray-400 mt-1 truncate">&quot;{email.body.slice(0, 80)}...&quot;</p>}
  </div>
);

const KBResultsCard = ({ results, style }) => {
  const [expanded, setExpanded] = useState(false);
  const items = results.items || [];
  const shown = expanded ? items : items.slice(0, 3);

  return (
    <div
      className="chat-tool-node border-l-4 border-l-violet-400 rounded-xl border border-gray-200 dark:border-gray-700/50 bg-white/90 dark:bg-gray-800/90 p-3"
      style={style}
    >
      <div className="flex items-center gap-2 mb-2">
        <Search size={14} className="text-violet-400" />
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">Knowledge Base</span>
        <span className="text-[10px] text-gray-400">· {items.length} results</span>
      </div>
      <div className="space-y-1">
        {shown.map((item, i) => (
          <div key={i} className="flex items-center justify-between text-xs">
            <span className="text-gray-700 dark:text-gray-300 truncate flex-1">
              {item.title || item.content?.slice(0, 50)}
            </span>
            {item.score != null && (
              <div className="flex items-center gap-1 ml-2 shrink-0">
                <div className="w-12 h-1.5 rounded-full bg-gray-200 dark:bg-gray-700 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-violet-400"
                    style={{ width: `${Math.round(item.score * 100)}%` }}
                  />
                </div>
                <span className="text-[10px] text-gray-400 w-6 text-right">{item.score.toFixed(2)}</span>
              </div>
            )}
          </div>
        ))}
      </div>
      {items.length > 3 && (
        <button
          onClick={() => setExpanded(!expanded)}
          className="mt-1.5 flex items-center gap-1 text-[10px] text-violet-400 hover:text-violet-300 transition cursor-pointer"
        >
          {expanded ? <ChevronUp size={10} /> : <ChevronDown size={10} />}
          {expanded ? 'Show less' : `Show ${items.length - 3} more`}
        </button>
      )}
    </div>
  );
};

const DataCard = ({ type, data, style }) => {
  switch (type) {
    case 'lead':
      return <LeadCard lead={data} style={style} />;
    case 'leads':
      return (data.items || []).map((lead, i) => (
        <LeadCard key={i} lead={lead} style={{ ...style, animationDelay: `${i * 100}ms` }} />
      ));
    case 'file':
      return <FileCard file={data} style={style} />;
    case 'email':
      return <EmailCard email={data} style={style} />;
    case 'kb_results':
      return <KBResultsCard results={data} style={style} />;
    default:
      return null;
  }
};

export default DataCard;
