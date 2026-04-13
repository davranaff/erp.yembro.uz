export type TourRouteMatcher = string | RegExp | ((pathname: string) => boolean);

export type TourAccessContext = {
  isAuthenticated: boolean;
  pathname: string;
  roles: readonly string[];
  permissions: readonly string[];
};

export type TourStepAutoAction = {
  type: 'click';
  selector: string;
  maxAttempts?: number;
  intervalMs?: number;
};

export type TourStepDefinition = {
  id: string;
  target: string;
  titleKey: string;
  descriptionKey: string;
  titleFallback: string;
  descriptionFallback: string;
  autoActions?: readonly TourStepAutoAction[];
  route?: TourRouteMatcher;
  requiredRoles?: readonly string[];
  requiredPermissions?: readonly string[];
  skipIfTargetMissing?: boolean;
};

export type TourDefinition = {
  id: string;
  version: number;
  titleKey: string;
  descriptionKey: string;
  titleFallback: string;
  descriptionFallback: string;
  route: TourRouteMatcher;
  priority?: number;
  autoStart?: boolean;
  allowUnauthenticated?: boolean;
  steps: readonly TourStepDefinition[];
  isAvailable?: (context: TourAccessContext) => boolean;
};

export type TourProgressState = {
  completed: Record<string, number>;
  dismissed: Record<string, number>;
};
