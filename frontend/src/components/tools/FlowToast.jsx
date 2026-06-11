import { useState, useEffect, useCallback } from 'react';

const FlowToast = ({ message, icon, visible, onHide }) => {
  useEffect(() => {
    if (!visible) return;
    const t = setTimeout(() => onHide(), 2500);
    return () => clearTimeout(t);
  }, [visible, onHide]);

  return (
    <div
      className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3.5 rounded-lg
        bg-paper border-[1.5px] border-rule
        shadow-ink text-sm font-medium text-ink
        transition-all duration-400
        ${visible
          ? 'translate-y-0 opacity-100'
          : 'translate-y-20 opacity-0 pointer-events-none'
        }`}
      style={{ transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)' }}
    >
      {icon && <span className="text-lg">{icon}</span>}
      <span>{message}</span>
    </div>
  );
};

export default FlowToast;

// eslint-disable-next-line react-refresh/only-export-components
export const useFlowToast = () => {
  const [toast, setToast] = useState({ message: '', icon: '', visible: false });

  const showToast = useCallback((icon, message) => {
    setToast({ icon, message, visible: true });
  }, []);

  const hideToast = useCallback(() => {
    setToast(prev => ({ ...prev, visible: false }));
  }, []);

  return { toast, showToast, hideToast };
};
