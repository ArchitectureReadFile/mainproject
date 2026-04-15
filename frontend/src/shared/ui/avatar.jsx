import { cn } from "@/shared/lib/utils"
import * as AvatarPrimitive from "@radix-ui/react-avatar"

function Avatar({ className, ...props }) {
  return (
    <AvatarPrimitive.Root
      className={cn("relative flex size-10 shrink-0 overflow-hidden rounded-full", className)}
      {...props}
    />
  )
}

function AvatarImage({ className, ...props }) {
  return (
    <AvatarPrimitive.Image
      className={cn("aspect-square size-full", className)}
      {...props}
    />
  )
}

function AvatarFallback({ className, ...props }) {
  return (
    <AvatarPrimitive.Fallback
      className={cn("bg-muted flex size-full items-center justify-center rounded-full", className)}
      {...props}
    />
  )
}

export { Avatar, AvatarFallback, AvatarImage }
