import { cn } from '@/lib/utils'
import * as TabsPrimitive from '@radix-ui/react-tabs'

const Tabs = TabsPrimitive.Root

function TabsList({ className, ...props }) {
  return (
    <TabsPrimitive.List
      className={cn(
        'inline-flex items-center gap-1 border-b border-border w-full pb-2',
        className
      )}
      {...props}
    />
  )
}

function TabsTrigger({ className, ...props }) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        'inline-flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-lg transition-colors',
        'text-muted-foreground hover:bg-muted hover:text-foreground',
        'data-[state=active]:bg-primary data-[state=active]:text-primary-foreground',
        'disabled:pointer-events-none disabled:opacity-50',
        className
      )}
      {...props}
    />
  )
}

function TabsContent({ className, ...props }) {
  return (
    <TabsPrimitive.Content
      className={cn('mt-6 outline-none', className)}
      {...props}
    />
  )
}

export { Tabs, TabsContent, TabsList, TabsTrigger }
