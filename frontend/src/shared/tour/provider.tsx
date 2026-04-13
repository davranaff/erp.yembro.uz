import {
  type CSSProperties,
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { useLocation } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { useAuthStore } from '@/shared/auth';
import { useI18n } from '@/shared/i18n';

import {
  isTourDefinitionAvailable,
  isTourStepAvailable,
  matchesTourRoute,
  TOUR_DEFINITIONS,
} from './config';
import {
  isTourCompleted,
  isTourDismissed,
  loadTourProgress,
  markTourCompleted,
  markTourDismissed,
  saveTourProgress,
} from './storage';
import type { TourAccessContext, TourDefinition, TourStepDefinition } from './types';

type TourContextValue = {
  isActive: boolean;
  hasContextTour: boolean;
  contextTourTitle: string;
  startContextTour: () => void;
  startTour: (tourId: string) => void;
};

const TourContext = createContext<TourContextValue | null>(null);

const TARGET_FIND_INTERVAL_MS = 140;
const TARGET_FIND_MAX_ATTEMPTS = 60;
const STEP_ACTION_DEFAULT_ATTEMPTS = 14;
const STEP_ACTION_DEFAULT_INTERVAL_MS = 120;
const HIGHLIGHT_PADDING = 8;
const TOUR_CARD_MARGIN = 16;
const TOUR_CARD_OFFSET = 14;

type HighlightRect = {
  top: number;
  left: number;
  width: number;
  height: number;
};

type TourCardPosition = {
  top: number;
  left: number;
};

const getDefinitionById = (tourId: string | null): TourDefinition | null => {
  if (!tourId) {
    return null;
  }

  return TOUR_DEFINITIONS.find((definition) => definition.id === tourId) ?? null;
};

const isHTMLElementVisible = (element: HTMLElement): boolean => {
  const rect = element.getBoundingClientRect();
  return rect.width > 0 && rect.height > 0;
};

const isHTMLElementInteractive = (element: HTMLElement): boolean => {
  const disabledAttr = element.getAttribute('disabled');
  const ariaDisabledAttr = element.getAttribute('aria-disabled');

  if (disabledAttr !== null || ariaDisabledAttr === 'true') {
    return false;
  }

  if ('disabled' in element && typeof element.disabled === 'boolean' && element.disabled) {
    return false;
  }

  return true;
};

const toHighlightRect = (element: HTMLElement): HighlightRect => {
  const rect = element.getBoundingClientRect();
  return {
    top: Math.max(0, rect.top - HIGHLIGHT_PADDING),
    left: Math.max(0, rect.left - HIGHLIGHT_PADDING),
    width: rect.width + HIGHLIGHT_PADDING * 2,
    height: rect.height + HIGHLIGHT_PADDING * 2,
  };
};

const queryVisibleElements = (selector: string): HTMLElement[] => {
  if (!selector.trim()) {
    return [];
  }

  return Array.from(document.querySelectorAll<HTMLElement>(selector)).filter((element) =>
    isHTMLElementVisible(element),
  );
};

const findCurrentTargetElement = (selector: string): HTMLElement | null =>
  queryVisibleElements(selector)[0] ?? null;

const findInteractiveTargetElement = (selector: string): HTMLElement | null =>
  queryVisibleElements(selector).find(isHTMLElementInteractive) ?? null;

const clamp = (value: number, min: number, max: number): number => {
  if (max < min) {
    return min;
  }

  return Math.min(Math.max(value, min), max);
};

const findStepIndex = (
  steps: readonly TourStepDefinition[],
  startIndex: number,
  direction: 1 | -1,
  isEligible: (step: TourStepDefinition) => boolean,
  includeStart = false,
): number => {
  let cursor = includeStart ? startIndex : startIndex + direction;

  while (cursor >= 0 && cursor < steps.length) {
    if (isEligible(steps[cursor])) {
      return cursor;
    }

    cursor += direction;
  }

  return -1;
};

const getContextualTour = (
  definitions: readonly TourDefinition[],
  pathname: string,
): TourDefinition | null => {
  const routeDefinitions = definitions
    .filter((definition) => matchesTourRoute(definition.route, pathname))
    .sort((left, right) => (right.priority ?? 0) - (left.priority ?? 0));

  return routeDefinitions[0] ?? null;
};

const EMPTY_AUTH_LIST: string[] = [];

export function TourProvider({ children }: PropsWithChildren) {
  const { t } = useI18n();
  const location = useLocation();
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const storedRoles = useAuthStore((state) => state.session?.roles);
  const storedPermissions = useAuthStore((state) => state.session?.permissions);
  const roles = storedRoles ?? EMPTY_AUTH_LIST;
  const permissions = storedPermissions ?? EMPTY_AUTH_LIST;

  const [progressState, setProgressState] = useState(() => loadTourProgress());
  const [activeTourId, setActiveTourId] = useState<string | null>(null);
  const [activeStepIndex, setActiveStepIndex] = useState(0);
  const [highlightRect, setHighlightRect] = useState<HighlightRect | null>(null);
  const [isLocatingTarget, setIsLocatingTarget] = useState(false);
  const [tourCardPosition, setTourCardPosition] = useState<TourCardPosition | null>(null);
  const activeStepIndexRef = useRef(0);
  const activeTargetSelectorRef = useRef('');
  const locateAttemptTokenRef = useRef(0);
  const tourCardRef = useRef<HTMLElement | null>(null);

  const accessContext = useMemo<TourAccessContext>(
    () => ({
      isAuthenticated,
      pathname: location.pathname,
      roles,
      permissions,
    }),
    [isAuthenticated, location.pathname, permissions, roles],
  );

  const availableDefinitions = useMemo(
    () =>
      TOUR_DEFINITIONS.filter((definition) => isTourDefinitionAvailable(definition, accessContext)),
    [accessContext],
  );

  const contextualDefinition = useMemo(
    () => getContextualTour(availableDefinitions, location.pathname),
    [availableDefinitions, location.pathname],
  );

  const activeDefinition = useMemo(() => getDefinitionById(activeTourId), [activeTourId]);

  const isStepEligible = useCallback(
    (step: TourStepDefinition): boolean => isTourStepAvailable(step, accessContext),
    [accessContext],
  );

  const eligibleStepIndexes = useMemo(() => {
    if (!activeDefinition) {
      return [] as number[];
    }

    return activeDefinition.steps.flatMap((step, index) => (isStepEligible(step) ? [index] : []));
  }, [activeDefinition, isStepEligible]);

  const activeStep = useMemo(() => {
    if (!activeDefinition) {
      return null;
    }

    if (!activeDefinition.steps[activeStepIndex]) {
      return null;
    }

    return activeDefinition.steps[activeStepIndex];
  }, [activeDefinition, activeStepIndex]);

  const currentStepNumber = useMemo(() => {
    if (!activeDefinition) {
      return 0;
    }

    const position = eligibleStepIndexes.indexOf(activeStepIndex);
    return position >= 0 ? position + 1 : 0;
  }, [activeDefinition, activeStepIndex, eligibleStepIndexes]);

  const totalEligibleSteps = eligibleStepIndexes.length;
  const isLastStep = currentStepNumber > 0 && currentStepNumber === totalEligibleSteps;

  const resolveCurrentEligibleStepIndex = useCallback(() => {
    if (eligibleStepIndexes.length === 0) {
      return -1;
    }

    const refIndex = activeStepIndexRef.current;
    if (eligibleStepIndexes.includes(refIndex)) {
      return refIndex;
    }

    if (eligibleStepIndexes.includes(activeStepIndex)) {
      return activeStepIndex;
    }

    return eligibleStepIndexes[0];
  }, [activeStepIndex, eligibleStepIndexes]);

  useEffect(() => {
    activeStepIndexRef.current = activeStepIndex;
  }, [activeStepIndex]);

  const clearTourState = useCallback(() => {
    setActiveTourId(null);
    setActiveStepIndex(0);
    activeStepIndexRef.current = 0;
    setHighlightRect(null);
    setIsLocatingTarget(false);
    setTourCardPosition(null);
    activeTargetSelectorRef.current = '';
  }, []);

  const closeTour = useCallback(
    (reason: 'dismissed' | 'completed') => {
      if (activeDefinition) {
        setProgressState((currentState) =>
          reason === 'completed'
            ? markTourCompleted(currentState, activeDefinition.id, activeDefinition.version)
            : markTourDismissed(currentState, activeDefinition.id, activeDefinition.version),
        );
      }

      clearTourState();
    },
    [activeDefinition, clearTourState],
  );

  const cancelTour = useCallback(() => {
    clearTourState();
  }, [clearTourState]);

  const goToPreviousStep = useCallback(() => {
    if (!activeDefinition || eligibleStepIndexes.length === 0) {
      return;
    }

    const currentIndex = resolveCurrentEligibleStepIndex();
    if (currentIndex === -1) {
      return;
    }

    const currentPosition = eligibleStepIndexes.indexOf(currentIndex);

    if (currentPosition <= 0) {
      return;
    }

    const previousIndex = eligibleStepIndexes[currentPosition - 1] ?? currentIndex;
    if (previousIndex === currentIndex) {
      return;
    }

    activeStepIndexRef.current = previousIndex;
    setActiveStepIndex(previousIndex);
  }, [activeDefinition, eligibleStepIndexes, resolveCurrentEligibleStepIndex]);

  const goToNextStep = useCallback(
    (reason: 'advance' | 'missing-target' = 'advance') => {
      if (!activeDefinition || eligibleStepIndexes.length === 0) {
        return;
      }

      const currentIndex = resolveCurrentEligibleStepIndex();
      if (currentIndex === -1) {
        return;
      }

      const currentPosition = eligibleStepIndexes.indexOf(currentIndex);
      const nextPosition = currentPosition === -1 ? 0 : currentPosition + 1;

      if (nextPosition >= eligibleStepIndexes.length) {
        closeTour('completed');
        return;
      }

      if (reason === 'missing-target') {
        setHighlightRect(null);
      }

      const nextIndex = eligibleStepIndexes[nextPosition] ?? currentIndex;
      if (nextIndex === currentIndex) {
        return;
      }

      activeStepIndexRef.current = nextIndex;
      setActiveStepIndex(nextIndex);
    },
    [activeDefinition, closeTour, eligibleStepIndexes, resolveCurrentEligibleStepIndex],
  );

  const startTour = useCallback(
    (tourId: string) => {
      const tourDefinition = availableDefinitions.find((definition) => definition.id === tourId);
      if (!tourDefinition) {
        return;
      }

      const firstEligibleStepIndex = findStepIndex(
        tourDefinition.steps,
        0,
        1,
        isStepEligible,
        true,
      );

      if (firstEligibleStepIndex === -1) {
        return;
      }

      setActiveTourId(tourDefinition.id);
      setActiveStepIndex(firstEligibleStepIndex);
      activeStepIndexRef.current = firstEligibleStepIndex;
      setHighlightRect(null);
      setIsLocatingTarget(false);
      setTourCardPosition(null);
      activeTargetSelectorRef.current = '';
    },
    [availableDefinitions, isStepEligible],
  );

  const startContextTour = useCallback(() => {
    if (!contextualDefinition) {
      return;
    }

    startTour(contextualDefinition.id);
  }, [contextualDefinition, startTour]);

  useEffect(() => {
    saveTourProgress(progressState);
  }, [progressState]);

  useEffect(() => {
    if (!activeDefinition) {
      return;
    }

    let eligibleIndex = findStepIndex(
      activeDefinition.steps,
      activeStepIndex,
      1,
      isStepEligible,
      true,
    );

    if (eligibleIndex === -1) {
      eligibleIndex = findStepIndex(
        activeDefinition.steps,
        activeStepIndex,
        -1,
        isStepEligible,
        true,
      );
    }

    if (eligibleIndex === -1) {
      closeTour('completed');
      return;
    }

    if (eligibleIndex !== activeStepIndex) {
      activeStepIndexRef.current = eligibleIndex;
      setActiveStepIndex(eligibleIndex);
    }
  }, [activeDefinition, activeStepIndex, closeTour, isStepEligible]);

  useEffect(() => {
    if (activeTourId) {
      return;
    }

    const autoStartDefinition = availableDefinitions
      .filter((definition) => definition.autoStart)
      .filter((definition) => matchesTourRoute(definition.route, location.pathname))
      .sort((left, right) => (right.priority ?? 0) - (left.priority ?? 0))
      .find(
        (definition) =>
          !isTourCompleted(progressState, definition.id, definition.version) &&
          !isTourDismissed(progressState, definition.id, definition.version),
      );

    if (!autoStartDefinition) {
      return;
    }

    startTour(autoStartDefinition.id);
  }, [activeTourId, availableDefinitions, location.pathname, progressState, startTour]);

  useEffect(() => {
    if (!activeDefinition) {
      return;
    }

    if (!matchesTourRoute(activeDefinition.route, location.pathname)) {
      cancelTour();
    }
  }, [activeDefinition, cancelTour, location.pathname]);

  useEffect(() => {
    if (!activeStep) {
      setHighlightRect(null);
      setIsLocatingTarget(false);
      activeTargetSelectorRef.current = '';
      return;
    }

    const locateAttemptToken = locateAttemptTokenRef.current + 1;
    locateAttemptTokenRef.current = locateAttemptToken;

    let isDisposed = false;
    let intervalId: number | null = null;
    let resizeObserver: ResizeObserver | null = null;
    let detachTargetListeners: (() => void) | null = null;
    let mutationObserver: MutationObserver | null = null;
    let attempts = 0;

    setHighlightRect(null);
    setIsLocatingTarget(true);

    const selector = activeStep.target.trim();
    activeTargetSelectorRef.current = selector;

    const findTarget = (): HTMLElement | null => findCurrentTargetElement(selector);

    const updateHighlightRect = () => {
      if (isDisposed) {
        return;
      }

      const target = findTarget();
      if (!target) {
        return;
      }

      setHighlightRect(toHighlightRect(target));
    };

    const bindTargetListeners = (target: HTMLElement) => {
      window.addEventListener('scroll', updateHighlightRect, true);
      window.addEventListener('resize', updateHighlightRect);

      const handleTransitionEnd = () => {
        updateHighlightRect();
      };

      target.addEventListener('transitionend', handleTransitionEnd);

      if (typeof ResizeObserver !== 'undefined') {
        resizeObserver = new ResizeObserver(() => {
          updateHighlightRect();
        });
        resizeObserver.observe(target);
      }

      return () => {
        target.removeEventListener('transitionend', handleTransitionEnd);
      };
    };

    const unbindTargetListeners = () => {
      window.removeEventListener('scroll', updateHighlightRect, true);
      window.removeEventListener('resize', updateHighlightRect);
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
    };

    const commitTarget = (target: HTMLElement) => {
      target.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'smooth' });
      setHighlightRect(toHighlightRect(target));
      setIsLocatingTarget(false);
      detachTargetListeners = bindTargetListeners(target);
    };

    const tryFindTarget = () => {
      if (isDisposed || locateAttemptTokenRef.current !== locateAttemptToken) {
        return;
      }

      const target = findTarget();
      if (target) {
        if (intervalId !== null) {
          window.clearInterval(intervalId);
          intervalId = null;
        }
        commitTarget(target);
        return;
      }

      attempts += 1;
      if (attempts < TARGET_FIND_MAX_ATTEMPTS) {
        return;
      }

      if (intervalId !== null) {
        window.clearInterval(intervalId);
        intervalId = null;
      }

      setIsLocatingTarget(false);
      setHighlightRect(null);

      if (activeStep.skipIfTargetMissing !== false) {
        goToNextStep('missing-target');
      }
    };

    const onDomMutation = () => {
      tryFindTarget();
    };

    tryFindTarget();
    intervalId = window.setInterval(tryFindTarget, TARGET_FIND_INTERVAL_MS);
    if (typeof MutationObserver !== 'undefined') {
      mutationObserver = new MutationObserver(onDomMutation);
      mutationObserver.observe(document.body, { childList: true, subtree: true });
    }

    return () => {
      isDisposed = true;
      locateAttemptTokenRef.current += 1;
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
      unbindTargetListeners();
      if (mutationObserver) {
        mutationObserver.disconnect();
        mutationObserver = null;
      }
      if (detachTargetListeners) {
        detachTargetListeners();
      }
    };
  }, [activeStep, goToNextStep]);

  useEffect(() => {
    if (!activeStep || typeof window === 'undefined') {
      return;
    }

    const actions = activeStep.autoActions ?? [];
    if (actions.length === 0) {
      return;
    }

    let disposed = false;
    let pendingTimeoutId: number | null = null;

    const clearPendingTimeout = () => {
      if (pendingTimeoutId === null) {
        return;
      }

      window.clearTimeout(pendingTimeoutId);
      pendingTimeoutId = null;
    };

    const wait = (ms: number) =>
      new Promise<void>((resolve) => {
        pendingTimeoutId = window.setTimeout(() => {
          pendingTimeoutId = null;
          resolve();
        }, ms);
      });

    const findCurrentTarget = (): HTMLElement | null => {
      const selector = activeStep.target.trim();
      return selector ? findCurrentTargetElement(selector) : null;
    };

    const runStepActions = async () => {
      for (const action of actions) {
        if (disposed || findCurrentTarget()) {
          return;
        }

        if (action.type !== 'click') {
          continue;
        }

        const maxAttempts = Math.max(1, action.maxAttempts ?? STEP_ACTION_DEFAULT_ATTEMPTS);
        const intervalMs = Math.max(40, action.intervalMs ?? STEP_ACTION_DEFAULT_INTERVAL_MS);

        for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
          if (disposed || findCurrentTarget()) {
            return;
          }

          const trigger = findInteractiveTargetElement(action.selector);
          if (trigger) {
            trigger.click();
            await wait(intervalMs);
            break;
          }

          if (attempt < maxAttempts - 1) {
            await wait(intervalMs);
          }
        }
      }
    };

    void runStepActions();

    return () => {
      disposed = true;
      clearPendingTimeout();
    };
  }, [activeStep]);

  useEffect(() => {
    if (!activeDefinition) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        closeTour('dismissed');
        return;
      }

      if (event.key === 'ArrowRight') {
        event.preventDefault();
        if (isLastStep) {
          closeTour('completed');
        } else {
          goToNextStep();
        }
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        goToPreviousStep();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [activeDefinition, closeTour, goToNextStep, goToPreviousStep, isLastStep]);

  useEffect(() => {
    if (!activeDefinition || !activeStep || typeof window === 'undefined') {
      setTourCardPosition(null);
      return;
    }

    const updateTourCardPosition = () => {
      const tourCardElement = tourCardRef.current;
      if (!tourCardElement) {
        return;
      }

      if (!highlightRect) {
        setTourCardPosition(null);
        return;
      }

      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;
      const cardRect = tourCardElement.getBoundingClientRect();

      const preferredTop = highlightRect.top + highlightRect.height + TOUR_CARD_OFFSET;
      const fallbackTop = highlightRect.top - cardRect.height - TOUR_CARD_OFFSET;
      const spaceBelow =
        viewportHeight - (highlightRect.top + highlightRect.height + TOUR_CARD_OFFSET);
      const spaceAbove = highlightRect.top - TOUR_CARD_OFFSET;

      const unclampedTop =
        spaceBelow >= cardRect.height || spaceBelow >= spaceAbove ? preferredTop : fallbackTop;

      const maxTop = viewportHeight - cardRect.height - TOUR_CARD_MARGIN;
      const maxLeft = viewportWidth - cardRect.width - TOUR_CARD_MARGIN;

      setTourCardPosition({
        top: clamp(unclampedTop, TOUR_CARD_MARGIN, maxTop),
        left: clamp(highlightRect.left, TOUR_CARD_MARGIN, maxLeft),
      });
    };

    const frameId = window.requestAnimationFrame(updateTourCardPosition);
    window.addEventListener('resize', updateTourCardPosition);

    return () => {
      window.cancelAnimationFrame(frameId);
      window.removeEventListener('resize', updateTourCardPosition);
    };
  }, [activeDefinition, activeStep, highlightRect, isLocatingTarget]);

  const contextValue = useMemo<TourContextValue>(
    () => ({
      isActive: Boolean(activeDefinition),
      hasContextTour: Boolean(contextualDefinition),
      contextTourTitle: contextualDefinition
        ? t(contextualDefinition.titleKey, undefined, contextualDefinition.titleFallback)
        : '',
      startContextTour,
      startTour,
    }),
    [activeDefinition, contextualDefinition, startContextTour, startTour, t],
  );

  const stepTitle = activeStep ? t(activeStep.titleKey, undefined, activeStep.titleFallback) : '';
  const stepDescription = activeStep
    ? t(activeStep.descriptionKey, undefined, activeStep.descriptionFallback)
    : '';
  const tourCardStyle: CSSProperties = tourCardPosition
    ? {
        top: `${tourCardPosition.top}px`,
        left: `${tourCardPosition.left}px`,
      }
    : {
        bottom: `${TOUR_CARD_MARGIN}px`,
        right: `${TOUR_CARD_MARGIN}px`,
      };

  return (
    <TourContext.Provider value={contextValue}>
      {children}

      {activeDefinition && activeStep && typeof document !== 'undefined'
        ? createPortal(
            <>
              {highlightRect ? (
                <div className="fixed inset-0 z-[110] bg-transparent" aria-hidden="true" />
              ) : (
                <div className="bg-slate-950/72 fixed inset-0 z-[110]" aria-hidden="true" />
              )}

              {highlightRect ? (
                <div
                  className="pointer-events-none fixed z-[111] rounded-[20px] border-2 border-primary/85 transition-all duration-200"
                  style={{
                    top: `${highlightRect.top}px`,
                    left: `${highlightRect.left}px`,
                    width: `${highlightRect.width}px`,
                    height: `${highlightRect.height}px`,
                    boxShadow:
                      '0 0 0 9999px rgba(2, 6, 23, 0.72), 0 0 0 2px hsl(var(--primary) / 0.38), 0 24px 64px -30px rgba(15, 23, 42, 0.55)',
                  }}
                />
              ) : null}

              <aside
                key={`${activeDefinition.id}:${activeStep.id}`}
                ref={tourCardRef}
                className="fixed z-[112] w-[min(26rem,calc(100vw-2rem))] rounded-[28px] border border-border/70 bg-card p-5 shadow-[0_32px_96px_-52px_rgba(15,23,42,0.55)]"
                style={tourCardStyle}
              >
                <div className="space-y-4">
                  <div className="flex justify-end">
                    <Button
                      type="button"
                      size="icon-xs"
                      variant="ghost"
                      className="rounded-full"
                      onClick={() => closeTour('dismissed')}
                      aria-label={t('tour.close', undefined, 'Закрыть тур')}
                    >
                      ×
                    </Button>
                  </div>

                  <div className="rounded-2xl border border-border/70 bg-background/90 px-4 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-foreground">{stepTitle}</p>
                      <span className="rounded-full border border-border/70 bg-card px-2.5 py-1 text-xs text-muted-foreground">
                        {t(
                          'tour.stepCounter',
                          {
                            current: currentStepNumber || 1,
                            total: Math.max(totalEligibleSteps, 1),
                          },
                          `Шаг ${currentStepNumber || 1} из ${Math.max(totalEligibleSteps, 1)}`,
                        )}
                      </span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {stepDescription}
                    </p>
                    {isLocatingTarget ? (
                      <p className="mt-2 text-xs text-muted-foreground">
                        {t('tour.locatingTarget', undefined, 'Ищем элемент текущего шага...')}
                      </p>
                    ) : null}
                  </div>

                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      className="rounded-full"
                      onClick={() => closeTour('dismissed')}
                    >
                      {t('tour.skip', undefined, 'Пропустить')}
                    </Button>
                    <div className="flex items-center gap-2">
                      <Button
                        type="button"
                        variant="outline"
                        className="rounded-full"
                        onClick={goToPreviousStep}
                        disabled={currentStepNumber <= 1}
                      >
                        {t('tour.previous', undefined, 'Назад')}
                      </Button>
                      <Button
                        type="button"
                        className="rounded-full"
                        onClick={() => {
                          if (isLastStep) {
                            closeTour('completed');
                            return;
                          }

                          goToNextStep();
                        }}
                      >
                        {isLastStep
                          ? t('tour.finish', undefined, 'Завершить')
                          : t('tour.next', undefined, 'Далее')}
                      </Button>
                    </div>
                  </div>
                </div>
              </aside>
            </>,
            document.body,
          )
        : null}
    </TourContext.Provider>
  );
}

export const useTour = (): TourContextValue => {
  const context = useContext(TourContext);

  if (!context) {
    throw new Error('useTour must be used inside TourProvider');
  }

  return context;
};
