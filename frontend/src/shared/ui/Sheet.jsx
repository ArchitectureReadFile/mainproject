import { cn } from '@/shared/lib/utils'
import { Drawer } from 'vaul'

function Sheet({ open, onOpenChange, children }) {
  return (
    <Drawer.Root
      open={open}
      onOpenChange={onOpenChange}
      direction="right"
      dismissible={true}
      noBodyStyles={true}
    >
      {children}
    </Drawer.Root>
  )
}

function SheetContent({ className, children, ...props }) {
  return (
    <Drawer.Portal>
      <Drawer.Overlay className="fixed inset-0 z-[1000] bg-black/45" />
      <Drawer.Content
        className={cn(
          'fixed top-0 right-0 z-[1001] h-dvh w-[min(86vw,320px)] bg-background border-l border-border shadow-xl flex flex-col',
          className
        )}
        {...props}
      >
        {children}
      </Drawer.Content>
    </Drawer.Portal>
  )
}

function SheetHeader({ className, ...props }) {
  return (
    <div
      className={cn('flex items-center justify-between px-6 py-5 border-b border-border shrink-0', className)}
      {...props}
    />
  )
}

function SheetTitle({ className, ...props }) {
  return (
    <Drawer.Title
      className={cn('text-lg font-bold text-foreground', className)}
      {...props}
    />
  )
}

function SheetDescription({ className, ...props }) {
  return (
    <Drawer.Description
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  )
}

export { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle }
