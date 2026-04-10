import { useState } from 'react';

const MaskedPasswordInput = ({ value, onChange, placeholder, onClear, disabled }) => {
  const [visible, setVisible] = useState(false);
  return (
    <div className="flex gap-2 items-center">
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder || 'sk-...'}
        disabled={disabled}
        className="flex-1 px-3 py-2 border border-ink/20 rounded-sm bg-cream text-ink font-mono text-sm disabled:opacity-50"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="px-2 py-2 text-xs border border-ink/20 rounded-sm hover:bg-ink/5"
        disabled={disabled}
      >
        {visible ? 'Hide' : 'Show'}
      </button>
      {onClear && (
        <button
          type="button"
          onClick={onClear}
          className="px-2 py-2 text-xs border border-ink/20 rounded-sm hover:bg-ink/5"
          disabled={disabled}
        >
          Clear
        </button>
      )}
    </div>
  );
};

export default MaskedPasswordInput;
