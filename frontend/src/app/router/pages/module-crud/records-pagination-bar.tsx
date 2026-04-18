import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';
import { cn } from '@/shared/lib/cn';

import { frostedPanelClassName } from '../module-crud-page.helpers';

export interface RecordsPaginationBarProps {
  totalCount: number;
  totalPages: number;
  currentPage: number;
  paginationItems: Array<number | string>;
  pageStatusLabel: string;
  currentPageRangeLabel: string;
  previousLabel: string;
  nextLabel: string;
  onChangePage: (updater: (page: number) => number) => void;
  onSelectPage: (page: number) => void;
}

export function RecordsPaginationBar({
  totalCount,
  totalPages,
  currentPage,
  paginationItems,
  pageStatusLabel,
  currentPageRangeLabel,
  previousLabel,
  nextLabel,
  onChangePage,
  onSelectPage,
}: RecordsPaginationBarProps) {
  if (totalCount === 0) {
    return null;
  }

  return (
    <div
      className={`${frostedPanelClassName} flex flex-col gap-3 px-4 py-4 lg:flex-row lg:items-center lg:justify-between`}
    >
      <div className="space-y-1 text-sm text-muted-foreground">
        <p>{pageStatusLabel}</p>
        <p>{currentPageRangeLabel}</p>
      </div>
      <Pagination className="mx-0 w-full justify-start sm:w-auto sm:justify-end">
        <PaginationContent>
          <PaginationItem>
            <PaginationPrevious
              href="#"
              text={previousLabel}
              className={cn(currentPage === 1 && 'pointer-events-none opacity-50')}
              onClick={(event) => {
                event.preventDefault();
                if (currentPage > 1) {
                  onChangePage((page) => Math.max(page - 1, 1));
                }
              }}
            />
          </PaginationItem>
          {paginationItems.map((item, index) => (
            <PaginationItem key={`${item}-${index}`}>
              {typeof item === 'number' ? (
                <PaginationLink
                  href="#"
                  isActive={item === currentPage}
                  onClick={(event) => {
                    event.preventDefault();
                    onSelectPage(item);
                  }}
                >
                  {item}
                </PaginationLink>
              ) : (
                <PaginationEllipsis />
              )}
            </PaginationItem>
          ))}
          <PaginationItem>
            <PaginationNext
              href="#"
              text={nextLabel}
              className={cn(currentPage === totalPages && 'pointer-events-none opacity-50')}
              onClick={(event) => {
                event.preventDefault();
                if (currentPage < totalPages) {
                  onChangePage((page) => Math.min(page + 1, totalPages));
                }
              }}
            />
          </PaginationItem>
        </PaginationContent>
      </Pagination>
    </div>
  );
}
