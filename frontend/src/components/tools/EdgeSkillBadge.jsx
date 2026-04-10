import ToolIcon from './ToolIcon';

const EdgeSkillBadge = ({ middleware, pathD, position = 0.5, onRemove }) => {
  const getPointOnPath = (d, t) => {
    const pathEl = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    pathEl.setAttribute('d', d);
    const len = pathEl.getTotalLength();
    return pathEl.getPointAtLength(t * len);
  };

  const pt = getPointOnPath(pathD, position);

  return (
    <div
      className="absolute flex items-center justify-center group"
      style={{
        left: pt.x,
        top: pt.y,
        transform: 'translate(-50%, -50%)',
        zIndex: 5,
        animation: 'skill-badge-pop 0.35s cubic-bezier(0.34, 1.56, 0.64, 1) both',
      }}
    >
      {/* Soft iris halo */}
      <div className="absolute w-10 h-10 rounded-full bg-iris/10
                      group-hover:bg-iris/20 transition-all duration-300" />

      {/* Badge circle — paper with iris ring */}
      <div
        className="w-8 h-8 rounded-full border-[1.5px] border-iris bg-paper
                   shadow-[0_2px_10px_rgba(45,42,38,0.08)]
                   flex items-center justify-center transition-all duration-200
                   group-hover:scale-110 group-hover:shadow-[0_2px_14px_rgba(155,126,216,0.28)]
                   cursor-default"
        title={middleware.skill_name}
      >
        <ToolIcon name={middleware.skill_icon} size={16} className="text-iris" />
      </div>

      {/* Skill name tooltip */}
      <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap
                      px-2 py-0.5 rounded-sm bg-ink text-cream font-mono text-[9px] font-medium
                      opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none
                      shadow-ink-sm tracking-wide">
        {middleware.skill_name}
      </div>

      {/* Remove button on hover */}
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(middleware.id);
          }}
          className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full border-[1.5px] border-rose bg-paper
                     text-rose flex items-center justify-center text-[10px] font-bold leading-none
                     opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer
                     hover:bg-rose-soft shadow-ink-sm"
          title="Remove"
        >
          ×
        </button>
      )}
    </div>
  );
};

export default EdgeSkillBadge;
