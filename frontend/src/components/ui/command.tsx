import { Search } from 'lucide-react';
import * as React from 'react';

import { cn } from '@/shared/lib/cn';

type CommandProps = React.ComponentPropsWithoutRef<'div'> & {
  shouldFilter?: boolean;
};

type CommandInputProps = Omit<React.ComponentPropsWithoutRef<'input'>, 'value'> & {
  value?: string;
  onValueChange?: (value: string) => void;
};

type CommandItemProps = Omit<React.ComponentPropsWithoutRef<'button'>, 'onSelect' | 'value'> & {
  value?: string;
  onSelect?: (value: string) => void;
};

const Command = React.forwardRef<HTMLDivElement, CommandProps>(
  ({ className, shouldFilter: _shouldFilter, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex h-full w-full flex-col overflow-hidden rounded-[24px] bg-transparent text-foreground',
        className,
      )}
      {...props}
    />
  ),
);

Command.displayName = 'Command';

const CommandInput = React.forwardRef<HTMLInputElement, CommandInputProps>(
  ({ className, onValueChange, onChange, value, ...props }, ref) => (
    <div className="flex items-center gap-2 rounded-2xl border border-border/75 bg-card px-3 shadow-[0_14px_34px_-28px_rgba(15,23,42,0.12)]">
      <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
      <input
        ref={ref}
        value={value}
        className={cn(
          'flex h-11 w-full rounded-2xl bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50',
          className,
        )}
        onChange={(event) => {
          onValueChange?.(event.target.value);
          onChange?.(event);
        }}
        {...props}
      />
    </div>
  ),
);

CommandInput.displayName = 'CommandInput';

const CommandList = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<'div'>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('max-h-72 overflow-y-auto overflow-x-hidden', className)}
      {...props}
    />
  ),
);

CommandList.displayName = 'CommandList';

const CommandEmpty = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<'div'>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-2xl border border-border/70 bg-card px-3 py-3 text-sm text-muted-foreground',
        className,
      )}
      {...props}
    />
  ),
);

CommandEmpty.displayName = 'CommandEmpty';

const CommandGroup = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<'div'>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('space-y-1', className)} {...props} />
  ),
);

CommandGroup.displayName = 'CommandGroup';

const CommandSeparator = React.forwardRef<HTMLDivElement, React.ComponentPropsWithoutRef<'div'>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('my-2 h-px bg-border/70', className)} {...props} />
  ),
);

CommandSeparator.displayName = 'CommandSeparator';

const CommandItem = React.forwardRef<HTMLButtonElement, CommandItemProps>(
  ({ className, onClick, onSelect, type = 'button', value, ...props }, ref) => (
    <button
      ref={ref}
      type={type}
      className={cn(
        'data-[selected=true]:bg-primary/8 relative flex cursor-default items-center gap-3 rounded-2xl border border-border/70 bg-card px-3 py-3 text-sm text-foreground outline-none transition data-[disabled=true]:pointer-events-none data-[selected=true]:border-primary/30 data-[disabled=true]:opacity-50',
        className,
      )}
      onClick={(event) => {
        onSelect?.(value ?? '');
        onClick?.(event);
      }}
      {...props}
    />
  ),
);

CommandItem.displayName = 'CommandItem';

export {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
};
