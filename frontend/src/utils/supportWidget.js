const SUPPORT_WIDGET_SCRIPT_ID = 'concierge-support-widget-script';
// URL скрипта віджета береться з env; якщо не заданий — віджет не підключається
const SUPPORT_WIDGET_SRC = import.meta.env.VITE_SUPPORT_WIDGET_URL || '';

// Додаємо / видаляємо віджет підтримки Concierge в залежності від типу клієнта
export const ensureSupportWidgetForClientType = (clientType) => {
  if (typeof document === 'undefined') return;

  const isWhiteLabel = clientType === 'white_label';
  const existingScript = document.getElementById(SUPPORT_WIDGET_SCRIPT_ID);

  // Для white label клієнтів віджет не показуємо
  if (isWhiteLabel) {
    if (existingScript) {
      existingScript.remove();
    }
    return;
  }

  // Для всіх НЕ white label клієнтів — показуємо один раз (якщо URL заданий)
  if (!existingScript && SUPPORT_WIDGET_SRC) {
    const script = document.createElement('script');
    script.id = SUPPORT_WIDGET_SCRIPT_ID;
    script.src = SUPPORT_WIDGET_SRC;
    script.async = true;
    document.head.appendChild(script);
  }
};

export const removeSupportWidget = () => {
  if (typeof document === 'undefined') return;
  const existingScript = document.getElementById(SUPPORT_WIDGET_SCRIPT_ID);
  if (existingScript) {
    existingScript.remove();
  }
};