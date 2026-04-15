import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { describe, expect, it } from 'vitest';

import { TOUR_DEFINITIONS } from './config';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SOURCE_ROOT = path.resolve(__dirname, '../..');

const EXCLUDED_SOURCE_FILES = new Set([
  path.resolve(SOURCE_ROOT, 'shared/i18n/messages.ts'),
  path.resolve(SOURCE_ROOT, 'shared/tour/config.ts'),
  path.resolve(SOURCE_ROOT, 'shared/tour/config.test.ts'),
]);

const collectSourceFiles = (directory: string): string[] =>
  fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const resolvedPath = path.join(directory, entry.name);

    if (entry.isDirectory()) {
      return collectSourceFiles(resolvedPath);
    }

    if (!/\.(ts|tsx)$/.test(entry.name) || /\.test\.(ts|tsx)$/.test(entry.name)) {
      return [];
    }

    if (EXCLUDED_SOURCE_FILES.has(resolvedPath)) {
      return [];
    }

    return [resolvedPath];
  });

const escapeRegExp = (value: string): string => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

const resolveTourSelectors = (): string[] => {
  const selectors = new Set<string>();

  for (const definition of TOUR_DEFINITIONS) {
    for (const step of definition.steps) {
      selectors.add(step.target);

      for (const action of step.autoActions ?? []) {
        selectors.add(action.selector);
      }
    }
  }

  return Array.from(selectors);
};

const extractDataTourValue = (selector: string): string | null => {
  const match = selector.match(/^\[data-tour="([^"]+)"\]$/);
  return match?.[1] ?? null;
};

const SOURCE_FILES = collectSourceFiles(SOURCE_ROOT);
const SOURCE_CONTENT = SOURCE_FILES.map((filePath) => fs.readFileSync(filePath, 'utf-8'));

const hasDataTourAnchorInSource = (dataTourValue: string): boolean => {
  const escapedValue = escapeRegExp(dataTourValue);
  const patterns = [
    new RegExp(`data-tour\\s*=\\s*["']${escapedValue}["']`),
    new RegExp(`dataTour\\s*=\\s*["']${escapedValue}["']`),
    new RegExp(`data-tour\\s*=\\s*\\{[^}]*["']${escapedValue}["'][^}]*\\}`),
    new RegExp(`dataTour\\s*=\\s*\\{[^}]*["']${escapedValue}["'][^}]*\\}`),
  ];

  return SOURCE_CONTENT.some((content) => patterns.some((pattern) => pattern.test(content)));
};

describe('tour config anchors', () => {
  it('keeps every data-tour selector aligned with JSX anchors', () => {
    const missingAnchors = resolveTourSelectors()
      .map((selector) => extractDataTourValue(selector))
      .filter((value): value is string => Boolean(value))
      .filter((value) => !hasDataTourAnchorInSource(value));

    expect(missingAnchors).toEqual([]);
  });
});
