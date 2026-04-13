export type DepartmentHierarchyRecord = {
  id?: string | number | null;
  parent_department_id?: string | number | null;
};

export type DepartmentTreeNode<T extends DepartmentHierarchyRecord> = {
  id: string;
  parentId: string;
  depth: number;
  rootId: string;
  label: string;
  record: T;
  children: DepartmentTreeNode<T>[];
};

const normalizeDepartmentId = (value: unknown): string => {
  if (typeof value === 'string' || typeof value === 'number') {
    return String(value);
  }

  return '';
};

export const buildDepartmentChildrenMap = <T extends DepartmentHierarchyRecord>(
  departments: T[],
): Map<string, string[]> => {
  const childrenMap = new Map<string, string[]>();

  for (const department of departments) {
    const departmentId = normalizeDepartmentId(department.id);
    const parentId = normalizeDepartmentId(department.parent_department_id);

    if (!departmentId || !parentId) {
      continue;
    }

    childrenMap.set(parentId, [...(childrenMap.get(parentId) ?? []), departmentId]);
  }

  return childrenMap;
};

export const buildDepartmentTree = <T extends DepartmentHierarchyRecord>(
  departments: T[],
  getLabel: (department: T) => string,
): DepartmentTreeNode<T>[] => {
  const nodeById = new Map<string, DepartmentTreeNode<T>>();

  for (const department of departments) {
    const departmentId = normalizeDepartmentId(department.id);

    if (!departmentId) {
      continue;
    }

    nodeById.set(departmentId, {
      id: departmentId,
      parentId: normalizeDepartmentId(department.parent_department_id),
      depth: 0,
      rootId: departmentId,
      label: getLabel(department),
      record: department,
      children: [],
    });
  }

  for (const node of nodeById.values()) {
    if (!node.parentId) {
      continue;
    }

    const parentNode = nodeById.get(node.parentId);
    if (!parentNode) {
      continue;
    }

    parentNode.children.push(node);
  }

  const roots = [...nodeById.values()]
    .filter((node) => !node.parentId || !nodeById.has(node.parentId))
    .sort((leftNode, rightNode) => leftNode.label.localeCompare(rightNode.label));

  const assignHierarchy = (node: DepartmentTreeNode<T>, depth: number, rootId: string) => {
    node.depth = depth;
    node.rootId = rootId;
    node.children.sort((leftNode, rightNode) => leftNode.label.localeCompare(rightNode.label));
    node.children.forEach((childNode) => assignHierarchy(childNode, depth + 1, rootId));
  };

  roots.forEach((rootNode) => assignHierarchy(rootNode, 0, rootNode.id));

  return roots;
};

export const flattenDepartmentTree = <T extends DepartmentHierarchyRecord>(
  roots: DepartmentTreeNode<T>[],
): DepartmentTreeNode<T>[] => {
  const nodes: DepartmentTreeNode<T>[] = [];

  const visitNode = (node: DepartmentTreeNode<T>) => {
    nodes.push(node);
    node.children.forEach(visitNode);
  };

  roots.forEach(visitNode);

  return nodes;
};
