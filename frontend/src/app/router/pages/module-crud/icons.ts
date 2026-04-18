import {
  ArrowLeftRight,
  ArrowRightLeft,
  Barcode,
  BarChart3,
  Bird,
  Briefcase,
  Building2,
  CalendarDays,
  CircleDollarSign,
  CreditCard,
  Factory,
  FileText,
  FlaskConical,
  FlaskRound,
  FolderOpen,
  IterationCcw,
  KeyRound,
  Landmark,
  LayoutGrid,
  Leaf,
  Network,
  Package,
  PackageMinus,
  PackagePlus,
  Receipt,
  Ruler,
  Scissors,
  ShieldCheck,
  Tag,
  Tags,
  Truck,
  UserCog,
  Users,
  Wallet,
  Warehouse,
} from 'lucide-react';

import { resolveResourceIconKey, type ResourceCategoryGroupId } from '../module-crud-page.helpers';

export const LUCIDE_ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  PackagePlus,
  PackageMinus,
  Barcode,
  Tag,
  Factory,
  Truck,
  ArrowRightLeft,
  Warehouse,
  Users,
  Receipt,
  UserCog,
  Briefcase,
  FolderOpen,
  CreditCard,
  Landmark,
  ArrowLeftRight,
  CircleDollarSign,
  Building2,
  Network,
  LayoutGrid,
  Bird,
  Ruler,
  Tags,
  ShieldCheck,
  KeyRound,
  CalendarDays,
  IterationCcw,
  FlaskConical,
  Leaf,
  FlaskRound,
  Scissors,
  Package,
  FileText,
};

export const getResourceIcon = (
  resourceKey: string,
): React.ComponentType<{ className?: string }> => {
  const iconKey = resolveResourceIconKey(resourceKey);
  return LUCIDE_ICON_MAP[iconKey] ?? FileText;
};

export const GROUP_ICON_MAP: Record<
  ResourceCategoryGroupId,
  React.ComponentType<{ className?: string }>
> = {
  finance: Wallet,
  people_clients: Users,
  warehouse: Warehouse,
  operations: LayoutGrid,
  catalogs: Tags,
  analytics: BarChart3,
};
