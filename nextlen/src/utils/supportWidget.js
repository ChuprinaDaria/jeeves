const SUPPORT_WIDGET_SCRIPT_ID = 'nexelin-support-widget-script';
// Скрипт віджета з фронтенду (app.nexelin.com), не з бекенду
const SUPPORT_WIDGET_SRC = 'https://app.nexelin.com/static/widget/chat.js?tag=b4e3f076-24b6-4fc4-a265-3e2f28cd8618&v=3';

// Додаємо / видаляємо віджет підтримки Nexelin в залежності від типу клієнта
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

  // Для всіх НЕ white label клієнтів — показуємо один раз
  if (!existingScript) {
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