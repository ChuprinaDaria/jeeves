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
      }}
    >
      {/* Badge circle */}
      <div
        className={`w-7 h-7 rounded-full border-2 border-white dark:border-gray-800 bg-white dark:bg-gray-800
          shadow-md flex items-center justify-center transition-transform group-hover:scale-125 cursor-default`}
        title={middleware.skill_name}
      >
        <ToolIcon name={middleware.skill_icon} className="w-3.5 h-3.5 text-primary-500" />
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
            hover:bg-red-600"
          title="Remove"
        >
          x
        </button>
      )}
    </div>
  );
};

export default EdgeSkillBadge;
