import { lazy, Suspense } from 'react';

const KnowledgeBaseCard = lazy(() => import('./KnowledgeBaseCard'));
const CrmCard = lazy(() => import('./CrmCard'));
const AnalyticsCard = lazy(() => import('./AnalyticsCard'));

const RICH_CARDS = {
  'rag-search': KnowledgeBaseCard,
  'crm': CrmCard,
  'analytics': AnalyticsCard,
};

const RichCardWrapper = ({ slug, clientId }) => {
  const CardComponent = RICH_CARDS[slug];
  if (!CardComponent) return null;

  return (
    <Suspense fallback={<div className="h-[90px] animate-pulse bg-gray-100 dark:bg-gray-700 rounded-lg" />}>
      <CardComponent clientId={clientId} />
    </Suspense>
  );
};

export default RichCardWrapper;
export const hasRichCard = (slug) => slug in RICH_CARDS;
