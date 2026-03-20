import {
  Mail, BookOpen, Users, Send, MessageSquare, MessageCircle, Smartphone,
  Globe, Bot, Plug2, Calendar, Star, Camera, Phone, Code, Zap,
  Database, Shield, Bell, FileText, Search, Settings, Link, Headphones,
  ShoppingCart, CreditCard, BarChart, PieChart, Inbox, Hash,
  Wrench,
} from 'lucide-react';

const ICON_MAP = {
  mail: Mail,
  'book-open': BookOpen,
  users: Users,
  send: Send,
  'message-square': MessageSquare,
  'message-circle': MessageCircle,
  smartphone: Smartphone,
  globe: Globe,
  bot: Bot,
  plug: Plug2,
  plug2: Plug2,
  calendar: Calendar,
  star: Star,
  camera: Camera,
  phone: Phone,
  code: Code,
  zap: Zap,
  database: Database,
  shield: Shield,
  bell: Bell,
  'file-text': FileText,
  search: Search,
  settings: Settings,
  link: Link,
  headphones: Headphones,
  'shopping-cart': ShoppingCart,
  'credit-card': CreditCard,
  'bar-chart': BarChart,
  'pie-chart': PieChart,
  inbox: Inbox,
  hash: Hash,
  wrench: Wrench,
};

const ToolIcon = ({ name, className = 'w-4 h-4' }) => {
  const Icon = ICON_MAP[name];
  if (Icon) return <Icon className={className} />;
  // Fallback: if it looks like an emoji or other content, render as-is
  if (name && name.length <= 2) return <span className={className}>{name}</span>;
  return <Wrench className={className} />;
};

export default ToolIcon;
