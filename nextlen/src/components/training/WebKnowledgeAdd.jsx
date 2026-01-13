import { useState, useEffect } from "react";
import { Globe, Loader2, CheckCircle, Clock } from "lucide-react";
import { clientAPI } from "../../api/client";

const WebKnowledgeAdd = () => {
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [webRequests, setWebRequests] = useState([]);

  // Load web requests list on mount and refresh statuses periodically
  useEffect(() => {
    // Initial load
    loadWebRequests();

    // Periodic refresh to keep statuses in sync with backend
    const intervalId = setInterval(() => {
      loadWebRequests();
    }, 15000); // кожні 15 секунд

    return () => clearInterval(intervalId);
  }, []);

  const loadWebRequests = async () => {
    try {
      const response = await clientAPI.getWebParsingRequests();
      // DRF ViewSet list returns array directly or object with 'results' if paginated
      const data = response.data;
      setWebRequests(Array.isArray(data) ? data : (data?.results || []));
    } catch (error) {
      console.error('Failed to load web requests:', error);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!url.trim()) {
      alert('Website URL is required');
      return;
    }

    setSubmitting(true);
    try {
      const response = await clientAPI.createWebParsingRequest({
        website_url: url.trim(),
        description: description.trim() || '',
      });

      // Reload requests to get updated list
      await loadWebRequests();
      
      // Clear form
      setUrl("");
      setDescription("");
      
      alert('Web parsing request submitted successfully!');
    } catch (error) {
      console.error('Failed to submit web parsing request:', error);
      alert('Failed to submit web parsing request');
    } finally {
      setSubmitting(false);
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="text-green-600 dark:text-green-400" />;
      case 'in_progress':
        return <Clock size={16} className="text-blue-600 dark:text-blue-400 animate-spin" />;
      case 'pending':
        return <Clock size={16} className="text-yellow-600 dark:text-yellow-400" />;
      default:
        return <Clock size={16} className="text-gray-600 dark:text-gray-400" />;
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'in_progress':
        return 'In Progress';
      case 'pending':
        return 'Pending';
      default:
        return 'Pending';
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'bg-green-50 dark:bg-green-900/30 border-green-200 dark:border-green-700 text-green-800 dark:text-green-300';
      case 'in_progress':
        return 'bg-blue-50 dark:bg-blue-900/30 border-blue-200 dark:border-blue-700 text-blue-800 dark:text-blue-300';
      case 'pending':
        return 'bg-yellow-50 dark:bg-yellow-900/30 border-yellow-200 dark:border-yellow-700 text-yellow-800 dark:text-yellow-300';
      default:
        return 'bg-gray-50 dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-800 dark:text-gray-300';
    }
  };

  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-4">
        <Globe size={20} className="text-primary-600 dark:text-primary-400" />
        <h3 className="text-lg font-semibold text-accent-900 dark:text-accent-100">
          Add Knowledge from Web
        </h3>
      </div>

      {/* Form for adding */}
      <form onSubmit={handleSubmit} className="space-y-4 mb-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Website URL
          </label>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://example.com"
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
            disabled={submitting}
            required
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
            Description
          </label>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Describe what you need from this website..."
            rows={3}
            className="w-full border border-gray-300 dark:border-gray-600 rounded-lg px-3 py-2 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
            disabled={submitting}
          />
        </div>

        <button
          type="submit"
          disabled={submitting || !url.trim()}
          className="w-full btn-primary flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {submitting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              <span>Submitting...</span>
            </>
          ) : (
            <>
              <Globe size={16} />
              <span>Submit Request</span>
            </>
          )}
        </button>
      </form>

      {/* List of web requests */}
      {webRequests.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300">
            Your Requests:
          </h4>
          {webRequests.map((request) => (
            <div
              key={request.id}
              className={`border rounded-lg p-4 ${getStatusColor(request.status)}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    {getStatusIcon(request.status)}
                    <span className="text-xs font-medium">
                      {getStatusText(request.status)}
                    </span>
                  </div>
                  <a
                    href={request.website_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline break-all"
                  >
                    {request.website_url}
                  </a>
                  {request.description && (
                    <p className="text-xs mt-2 text-gray-600 dark:text-gray-400 line-clamp-2">
                      {request.description}
                    </p>
                  )}
                  {request.status === 'completed' && request.knowledge_block_name && (
                    <p className="text-xs mt-2 font-medium">
                      Knowledge block created: {request.knowledge_block_name}
                    </p>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default WebKnowledgeAdd;

