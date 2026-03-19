import { useRef, useState, useEffect } from 'react';
import FlipToolCard from './FlipToolCard';

const ToolCatalogStrip = ({ tools, onConnected, onToolHover, onToolHoverEnd }) => {
  const scrollRef = useRef(null);
  const [showLeftFade, setShowLeftFade] = useState(false);
  const [showRightFade, setShowRightFade] = useState(false);

  const updateFades = () => {
    const el = scrollRef.current;
    if (!el) return;
    setShowLeftFade(el.scrollLeft > 10);
    setShowRightFade(el.scrollLeft < el.scrollWidth - el.clientWidth - 10);
  };

  useEffect(() => {
    updateFades();
    const el = scrollRef.current;
    el?.addEventListener('scroll', updateFades);
    window.addEventListener('resize', updateFades);
    return () => {
      el?.removeEventListener('scroll', updateFades);
      window.removeEventListener('resize', updateFades);
    };
  }, [tools]);

  return (
    <div className="relative">
      {/* Left fade */}
      {showLeftFade && (
        <div className="absolute left-0 top-0 bottom-0 w-12 bg-gradient-to-r from-gray-50 dark:from-gray-900 to-transparent z-10 pointer-events-none" />
      )}
      {/* Right fade */}
      {showRightFade && (
        <div className="absolute right-0 top-0 bottom-0 w-12 bg-gradient-to-l from-gray-50 dark:from-gray-900 to-transparent z-10 pointer-events-none" />
      )}

      <div
        ref={scrollRef}
        className="flex gap-3 overflow-x-auto pb-2 px-1 scrollbar-hide"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {tools.map(tool => (
          <FlipToolCard
            key={tool.slug}
            tool={tool}
            onConnected={onConnected}
            onMouseEnter={onToolHover}
            onMouseLeave={onToolHoverEnd}
          />
        ))}
      </div>
    </div>
  );
};

export default ToolCatalogStrip;
