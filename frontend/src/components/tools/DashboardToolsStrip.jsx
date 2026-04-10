import { useState, useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, CheckCircle } from '@phosphor-icons/react';
import { toolsAPI } from '../../api/tools';
import ToolIcon from './ToolIcon';

const DashboardToolsStrip = () => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { tag: routeTag } = useParams();
  const [searchParams] = useSearchParams();
  const [tools, setTools] = useState([]);

  const tag = routeTag || searchParams.get('tag');

  useEffect(() => {
    toolsAPI.getMyTools()
      .then((res) => setTools(res.data))
      .catch(() => {}); // Silent fail — strip is optional
  }, []);

  if (tools.length === 0) return null;

  const toolsPath = routeTag ? `/l/${routeTag}/tools` : (tag ? `/tools?tag=${tag}` : '/tools');

  return (
    <div className="bg-paper rounded-lg border-[1.5px] border-rule p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="label-mono">
          {t('tools.connectedTools')} ({tools.length})
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {tools.map((conn) => (
          <button
            key={conn.tool.slug}
            onClick={() => navigate(toolsPath)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-linen hover:bg-mist border-[1.5px] border-rule transition-colors text-sm text-ink cursor-pointer"
          >
            <ToolIcon name={conn.tool.icon} className="w-4 h-4" />
            <span>{conn.tool.name}</span>
            <CheckCircle weight="light" size={14} className="text-sage" />
          </button>
        ))}
        <button
          onClick={() => navigate(toolsPath)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded border-[1.5px] border-dashed border-rule hover:border-iris hover:bg-linen transition-colors text-sm text-slate cursor-pointer"
        >
          <Plus weight="light" size={14} />
          {t('tools.addMore')}
        </button>
      </div>
    </div>
  );
};

export default DashboardToolsStrip;
