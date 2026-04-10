/**
 * Jeeves signature — a proper butler top hat.
 * Hairline stroke in currentColor so it composes with text-iris, text-sage etc.
 * Accepts `size`, `weight` (ignored, kept for Phosphor API compatibility), `className`.
 */
const JeevesHat = ({ size = 24, className = '', ...rest }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 32 32"
    fill="none"
    stroke="currentColor"
    strokeWidth="1.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    aria-hidden="true"
    {...rest}
  >
    {/* Crown of the hat — slight taper, like a proper tophat */}
    <path d="M10 7.5 L10 19 L22 19 L22 7.5 C22 6.67 21.1 6 20 6 L12 6 C10.9 6 10 6.67 10 7.5 Z" />
    {/* Brim — wider than the crown, sitting on the head */}
    <path d="M6 19.5 Q6 22 8 22 L24 22 Q26 22 26 19.5" />
    {/* Hat band — subtle detail above the brim */}
    <line x1="10" y1="17" x2="22" y2="17" />
  </svg>
);

export default JeevesHat;
