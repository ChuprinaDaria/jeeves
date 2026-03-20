import { useState, useEffect } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Plus, CheckCircle } from 'lucide-react';
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
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
          {t('tools.connectedTools')} ({tools.length})
        </h3>
      </div>
      <div className="flex flex-wrap gap-2">
        {tools.map((conn) => (
          <button
            key={conn.tool.slug}
            onClick={() => navigate(toolsPath)}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-50 dark:bg-gray-700/50 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-sm"
          >
            <ToolIcon name={conn.tool.icon} className="w-4 h-4" />
            <span className="text-gray-700 dark:text-gray-300">{conn.tool.name}</span>
            <CheckCircle className="w-3.5 h-3.5 text-green-500" />
          </button>
        ))}
        <button
          onClick={() => navigate(toolsPath)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-dashed border-gray-300 dark:border-gray-600 hover:border-primary-400 hover:bg-primary-50 dark:hover:bg-primary-900/20 transition-colors text-sm text-gray-500 dark:text-gray-400"
        >
          <Plus className="w-3.5 h-3.5" />
          {t('tools.addMore')}
        </button>
      </div>
    </div>
  );
};

export default DashboardToolsStrip;
