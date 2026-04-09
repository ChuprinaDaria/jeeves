import { Check, Loader2 } from 'lucide-react';

const ThinkingPipeline = ({ steps = [], currentStep = null }) => {
  const displaySteps = steps.length > 0 ? steps : [
    { id: 'thinking', label: 'AI Processing', status: currentStep === 'thinking' ? 'active' : 'pending' },
  ];

  // Compact mode for >3 steps
  if (displaySteps.length > 3) {
    const activeIndex = displaySteps.findIndex(s => s.status === 'active');
    const active = displaySteps[activeIndex] || displaySteps[displaySteps.length - 1];
    return (
      <div className="flex items-center gap-2 px-3 py-2">
        <Loader2 size={12} className="text-violet-400 animate-spin" />
        <span className="text-xs text-gray-400">
          Step {activeIndex + 1}/{displaySteps.length}: {active.label}...
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1 px-1 py-2 overflow-x-auto">
      {displaySteps.map((step, i) => (
        <div key={step.id} className="flex items-center gap-1 shrink-0">
          {i > 0 && (
            <div className={`w-6 h-px ${
              step.status === 'done'
                ? 'bg-violet-400/40'
                : step.status === 'active'
                ? 'bg-gradient-to-r from-violet-400/40 to-violet-400/10'
                : 'bg-gray-600'
            }`} />
          )}
          <div className={`flex items-center gap-1 px-2 py-1 rounded-full text-[10px] border transition-all ${
            step.status === 'active'
              ? 'border-violet-400/40 bg-violet-500/10 text-violet-300'
              : step.status === 'done'
              ? 'border-gray-600 bg-transparent text-gray-500'
              : 'border-gray-700 bg-transparent text-gray-600'
          }`}>
            {step.status === 'done' && <Check size={8} className="text-violet-400" />}
            {step.status === 'active' && <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-pulse" />}
            {step.label}
          </div>
        </div>
      ))}
    </div>
  );
};

export default ThinkingPipeline;
