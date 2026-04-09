import ToolIcon from './ToolIcon';

const EdgeSkillBadge = ({ middleware, pathD, position = 0.5, onRemove }) => {
  // Calculate point on bezier at given position (0-1)
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
      {/* Outer glow ring */}
      <div className="absolute w-10 h-10 rounded-full bg-primary-400/10 dark:bg-primary-500/10 group-hover:bg-primary-400/20 transition-all duration-300" />

      {/* Badge circle */}
      <div
        className={`w-8 h-8 rounded-full border-2 border-white dark:border-gray-800 bg-white dark:bg-gray-800
          shadow-[0_2px_8px_rgba(108,92,231,0.2)] dark:shadow-[0_2px_8px_rgba(108,92,231,0.3)]
          flex items-center justify-center transition-all duration-200
          group-hover:scale-110 group-hover:shadow-[0_2px_12px_rgba(108,92,231,0.35)]
          cursor-default`}
        title={middleware.skill_name}
      >
        <ToolIcon name={middleware.skill_icon} className="w-4 h-4 text-primary-500" />
      </div>

      {/* Skill name tooltip on hover */}
      <div className="absolute -bottom-7 left-1/2 -translate-x-1/2 whitespace-nowrap
        px-2 py-0.5 rounded-md bg-gray-900 dark:bg-gray-700 text-white text-[9px] font-medium
        opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none
        shadow-sm">
        {middleware.skill_name}
      </div>

      {/* Remove button on hover */}
      {onRemove && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            onRemove(middleware.id);
          }}
          className="absolute -top-1.5 -right-1.5 w-4 h-4 rounded-full bg-red-500 text-white
            flex items-center justify-center text-[9px] font-bold
            opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer
            hover:bg-red-600 shadow-sm"
          title="Remove"
        >
          x
        </button>
      )}
    </div>
  );
};

export default EdgeSkillBadge;
