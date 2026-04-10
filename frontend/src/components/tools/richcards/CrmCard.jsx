import { User, Buildings, Clock } from '@phosphor-icons/react';

const CrmCard = () => (
  <div className="space-y-1.5 py-1">
    <div className="flex items-center gap-1.5">
      <User size={12} weight="light" className="text-rose" />
      <span className="font-mono text-[10px] text-slate uppercase tracking-wide">Latest Contact</span>
    </div>
    <div className="px-2 py-1.5 rounded-sm bg-linen border-[1px] border-rule space-y-1">
      <div className="text-[10px] text-slate flex items-center gap-1">
        <Buildings size={10} weight="light" />
        <span>Awaiting CRM data…</span>
      </div>
      <div className="font-mono text-[9px] text-fog flex items-center gap-1 uppercase tracking-wide">
        <Clock size={10} weight="light" />
        <span>Connect CRM to see contacts</span>
      </div>
    </div>
  </div>
);

export default CrmCard;
