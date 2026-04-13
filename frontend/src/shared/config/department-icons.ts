import {
  Archive,
  Building2,
  Box,
  Briefcase,
  Coins,
  Egg,
  Factory,
  Leaf,
  Package,
  Pill,
  Shield,
  Users,
  type LucideIcon,
} from 'lucide-react';

export type DepartmentIconKey =
  | 'egg'
  | 'building'
  | 'coins'
  | 'factory'
  | 'package'
  | 'pill'
  | 'shield'
  | 'users'
  | 'box'
  | 'briefcase'
  | 'leaf'
  | 'archive';

type DepartmentIconOption = {
  key: DepartmentIconKey;
  icon: LucideIcon;
};

export const departmentIconOptions: DepartmentIconOption[] = [
  { key: 'building', icon: Building2 },
  { key: 'coins', icon: Coins },
  { key: 'egg', icon: Egg },
  { key: 'factory', icon: Factory },
  { key: 'package', icon: Package },
  { key: 'pill', icon: Pill },
  { key: 'shield', icon: Shield },
  { key: 'users', icon: Users },
  { key: 'box', icon: Box },
  { key: 'briefcase', icon: Briefcase },
  { key: 'leaf', icon: Leaf },
  { key: 'archive', icon: Archive },
];

const departmentIconMap = new Map(
  departmentIconOptions.map((option) => [option.key, option.icon] as const),
);

export const getDepartmentIcon = (
  iconKey?: string | null,
  fallbackIconKey?: string | null,
): LucideIcon | null => {
  if (iconKey && departmentIconMap.has(iconKey as DepartmentIconKey)) {
    return departmentIconMap.get(iconKey as DepartmentIconKey) ?? null;
  }

  if (fallbackIconKey && departmentIconMap.has(fallbackIconKey as DepartmentIconKey)) {
    return departmentIconMap.get(fallbackIconKey as DepartmentIconKey) ?? null;
  }

  return null;
};
