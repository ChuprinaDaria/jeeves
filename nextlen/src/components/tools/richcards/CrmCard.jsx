import { User, Building2, Clock } from 'lucide-react';

const CrmCard = () => (
  <div className="space-y-1.5 py-1">
    <div className="flex items-center gap-1.5">
      <User className="w-3 h-3 text-pink-400" />
      <span className="text-[10px] text-gray-300 font-medium">Latest Contact</span>
    </div>
    <div className="px-2 py-1.5 rounded-lg bg-gray-800/60 space-y-1">
      <div className="text-[10px] text-gray-400 flex items-center gap-1">
        <Building2 className="w-2.5 h-2.5" />
        <span>Awaiting CRM data...</span>
      </div>
      <div className="text-[9px] text-gray-500 flex items-center gap-1">
        <Clock className="w-2.5 h-2.5" />
        <span>Connect CRM to see contacts</span>
      </div>
    </div>
  </div>
);

export default CrmCard;
