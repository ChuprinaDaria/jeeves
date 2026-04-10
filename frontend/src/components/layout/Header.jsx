import LanguageSwitcher from '../common/LanguageSwitcher';

/**
 * Thin top bar. Just holds the language switcher now — the page greeting
 * lives inside each page so it can carry page-specific metadata.
 */
const Header = () => (
  <header className="h-14 flex items-center justify-end px-6 border-b border-rule bg-cream">
    <LanguageSwitcher />
  </header>
);

export default Header;
