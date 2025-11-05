import { RefreshCw, CheckCircle } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { clientAPI } from "../../api/client";

const SyncActions = ({ onSync }) => {
  const { t } = useTranslation();
  const [syncing, setSyncing] = useState(false);
  const [retraining, setRetraining] = useState(false);
  const [message, setMessage] = useState(null);

  const showMessage = (msg, isError = false) => {
    setMessage({ text: msg, isError });
    setTimeout(() => setMessage(null), 5000);
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const response = await clientAPI.syncData();
      const count = response.data?.documents_count || 0;
      const msg = response.data?.message || `Indexing started for ${count} new document(s)`;
      showMessage(msg, false);
      
      // Оновити список файлів після індексації
      if (onSync) {
        setTimeout(() => onSync(), 2000);
      }
    } catch (error) {
      console.error("Failed to sync data:", error);
      const errorMsg = error.response?.data?.message || error.response?.data?.error || "Failed to sync data";
      showMessage(errorMsg, true);
    } finally {
      setSyncing(false);
    }
  };

  const handleRetrain = async () => {
    setRetraining(true);
    try {
      const response = await clientAPI.reindexData();
      const count = response.data?.documents_count || 0;
      const msg = response.data?.message || `Reindexing started for ${count} document(s)`;
      showMessage(msg, false);
      
      // Оновити список файлів після реіндексації
      if (onSync) {
        setTimeout(() => onSync(), 2000);
      }
    } catch (error) {
      console.error("Failed to retrain:", error);
      const errorMsg = error.response?.data?.message || error.response?.data?.error || "Failed to retrain";
      showMessage(errorMsg, true);
    } finally {
      setRetraining(false);
    }
  };

  return (
    <div className="space-y-3">
      {/* Toast notification */}
      {message && (
        <div
          className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm ${
            message.isError
              ? "bg-red-50 text-red-800 border border-red-200"
              : "bg-green-50 text-green-800 border border-green-200"
          }`}
        >
          {!message.isError && <CheckCircle size={16} />}
          <span>{message.text}</span>
        </div>
      )}

      <div className="flex gap-3">
        <button
          onClick={handleSync}
          disabled={syncing || retraining}
          className="flex items-center gap-2 border rounded-lg px-4 py-2 hover:bg-gray-100 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw size={18} className={syncing ? "animate-spin" : ""} />
          {syncing ? t("syncActions.syncing") || "Syncing..." : t("syncActions.sync") || "Sync New Data"}
        </button>

        <button
          onClick={handleRetrain}
          disabled={syncing || retraining}
          className="flex items-center gap-2 bg-gradient-to-r from-indigo-500 to-purple-500 text-white rounded-lg px-4 py-2 hover:opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw size={18} className={retraining ? "animate-spin" : ""} />
          {retraining ? t("syncActions.retraining") || "Retraining..." : t("syncActions.retrain") || "Retrain Now"}
        </button>
      </div>
    </div>
  );
};

export default SyncActions;
